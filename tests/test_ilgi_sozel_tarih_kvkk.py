"""
Yapısal İlgi denetimi + sözel tarih çıkarımı + KVKK veri-sinyali köprüsü
birim testleri.

Bu üç ilkesel düzeltme, adversarial tutulmuş set (v3) hata analizinde
saptanan sınırlılıkları giderir; testler davranışı doğrudan (sistem
çıktısına bakılmadan kurgulanmış örneklerle) doğrular:

  1. İlgi ALAN ETİKETİ iki nokta ile tanımlıdır; gövdedeki düz cümle
     atıfları ("İlgi (b)'de kayıtlı yazınız") İlgi bloğu sayılmaz
     (kopuk İlgi zincirinin yapısal tespiti).
  2. Rakamsal tarih içermeyen belgelerde sözel tarih ("<Ay> ayının
     <gün-yazı> günü") evrak tarihi olarak çözülür.
  3. Gövdede gerçek kişiye ait kişisel veri (doğrulanmış T.C. kimlik
     numarası / IBAN) saptandıysa 6698 sayılı KVKK, "kişisel/kvkk"
     sözcükleri geçmese bile öneri listesinin ilk üçüne alınır.
"""

from __future__ import annotations

from src.agents.info_extraction_agent import (
    InfoExtractionAgent,
    sozel_tarih_bul,
)
from src.agents.legislation_agent import LegislationAgent
from src.agents.missing_info_agent import MissingInfoAgent
from src.agents.orchestrator import AgentState


# ----------------------------------------------------------------------
# 1. Sözel (yazıyla) tarih çıkarımı
# ----------------------------------------------------------------------
class TestSozelTarih:
    def test_ay_gununun_yazili_bicimi(self):
        assert sozel_tarih_bul(
            "İki bin yirmi altı yılı Temmuz ayının on ikinci günü toplanıldı."
        ) == "12 Temmuz 2026"

    def test_yil_yoksa_gun_ay_doner(self):
        assert sozel_tarih_bul("Mart ayının yirmi beşinci günü") == "25 Mart"

    def test_otuz_birinci_gun(self):
        assert sozel_tarih_bul("Ağustos ayının otuz birinci günü") == "31 Ağustos"

    def test_birinci_gun(self):
        assert sozel_tarih_bul("Nisan ayının birinci günü") == "01 Nisan"

    def test_onuncu_gun_tek_sozcuk(self):
        assert sozel_tarih_bul("Ekim ayının onuncu günü") == "10 Ekim"

    def test_tarihsiz_metin_bos_doner(self):
        assert sozel_tarih_bul("Bu metinde hiçbir tarih yoktur.") == ""

    def test_bilinmeyen_gun_sozcugu_uretmez(self):
        # "iş" gün sözcüğü değildir → ifade çözülemez, tarih üretilmez
        assert sozel_tarih_bul("Mayıs ayının filanca günü") == ""

    def test_rakamsal_tarih_iceren_tutanak_evrak_tarihi(self):
        """Sözel tarih, rakamsal tarih içermeyen tutanakta evrak tarihi olur."""
        metin = (
            "MUAYENE VE KABUL TUTANAĞI\n\n"
            "İki bin yirmi altı yılı Temmuz ayının on ikinci günü, depoda "
            "toplanılarak muayene yapılmış ve iş bu tutanak mahallinde iki "
            "nüsha olarak tanzim edilmiştir.\n"
        )
        ie = InfoExtractionAgent()
        assert ie._extract_document_date(metin) == "12 Temmuz 2026"

    def test_sozel_tarihli_tutanakta_tarih_eksik_sayilmaz(self):
        """Sözel tarih varsa eksik bilgi 'tarih' üretmemeli."""
        metin = (
            "KAVAKDÜZÜ KAYMAKAMLIĞI\nMUAYENE VE KABUL TUTANAĞI\n"
            "Saat : 10.15 - 11.40\nYer : Depo\n"
            "Konu : Muayene kabul\n"
            "İki bin yirmi altı yılı Temmuz ayının on ikinci günü toplanılarak "
            "muayene yapılmış ve iş bu tutanak tanzim edilmiştir.\n"
            "İmzalar:\n(imzalıdır) (imzalıdır) (imzalıdır)\n"
        )
        ie = InfoExtractionAgent()
        state = AgentState(raw_text=metin, classification={"tur": "tutanak"})
        ie.run(state)
        MissingInfoAgent().run(state)
        eksik_alanlar = {e["alan"] for e in state.missing_info}
        assert "tarih" not in eksik_alanlar


# ----------------------------------------------------------------------
# 2. Yapısal İlgi denetimi (alan etiketi vs. gövde atfı)
# ----------------------------------------------------------------------
class TestYapisalIlgi:
    def _ie(self) -> InfoExtractionAgent:
        return InfoExtractionAgent()

    def test_gercek_ilgi_blogu_cikarilir(self):
        metin = (
            "Sayı : E-123\n"
            "İlgi : a) 19.06.2026 tarihli ve E-40312578 sayılı yazınız\n"
            "       b) 03.07.2026 tarihli arıza bildirim formu\n\n"
            "Gereğini arz ederim.\n"
        )
        refs = self._ie()._extract_ilgi_references(metin)
        assert len(refs) == 2
        assert refs[0].startswith("a)")
        assert refs[1].startswith("b)")

    def test_govde_atfi_ilgi_blogu_sayilmaz(self):
        """İki nokta olmayan gövde atfı İlgi bloğu üretmez (kopuk zincir)."""
        metin = (
            "Sayı : E-999\n\n"
            "İlgi (b)'de kayıtlı yazınızla; ek ödenek talep edilmiştir.\n"
            "Gereğini rica ederim.\n"
        )
        assert self._ie()._extract_ilgi_references(metin) == []

    def test_ilgili_sozcugu_ile_baslayan_cumle_yakalanmaz(self):
        metin = "İlgili eylem planı ekte sunulmakta olup gereğini rica ederim.\n"
        assert self._ie()._extract_ilgi_references(metin) == []

    def test_kopuk_ilgi_cevap_yazisinda_eksik_isaretlenir(self):
        """Yalnız gövde atfı olan cevap yazısında 'ilgi' eksik sayılmalı."""
        metin = (
            "T.C.\nAKÇOVA KAYMAKAMLIĞI\nMali Hizmetler Müdürlüğü\n"
            "Sayı : E-52816409-841-2026/77\nKonu : Ek ödenek\n\n"
            "KAYMAKAMLIK MAKAMINA\n\n"
            "İlgi (b)'de kayıtlı yazınızla talep edilen ek ödenek "
            "değerlendirilmiştir.\n\nArz ederim.\n\nMüdür\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "cevap_yazisi"})
        InfoExtractionAgent().run(state)
        MissingInfoAgent().run(state)
        assert "ilgi" in {e["alan"] for e in state.missing_info}

    def test_gercek_ilgi_blogu_eksik_isaretlenmez(self):
        metin = (
            "T.C.\nPUSLUPINAR VALİLİĞİ\nBilgi İşlem Müdürlüğü\n"
            "Sayı : E-40312578-710-2026/402\nTarih : 08.07.2026\n"
            "Konu : Ağ altyapısı\n"
            "İlgi : a) 19.06.2026 tarihli ve E-40312578 sayılı yazınız\n\n"
            "KAYMAKAMLIK MAKAMINA\n\n"
            "İlgi (a) yazınızla duyurulan tedbirler kapsamında gereğini arz "
            "ederim.\n\nMüdür\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "ust_yazi"})
        InfoExtractionAgent().run(state)
        MissingInfoAgent().run(state)
        assert "ilgi" not in {e["alan"] for e in state.missing_info}


# ----------------------------------------------------------------------
# 3. KVKK veri-sinyali köprüsü
# ----------------------------------------------------------------------
class TestKvkkKoprusu:
    # Kurgu, checksum-geçerli T.C. kimlik numarası (gerçek kişiye ait değildir)
    GECERLI_TCKN = "56375893488"
    ORNEK_IBAN = "TR33 0006 1005 1978 6457 8413 26"

    def _mevzuat_doc_idleri(self, state) -> list:
        return [m.get("doc_id") for m in (state.legislation_matches or [])]

    def test_tckn_6698_ilk_uce_alir(self):
        metin = (
            "HASAR TESPİT TUTANAĞI\n"
            "Özel araç sürücüsü Selim GÖLGELİKAYA (T.C. Kimlik No: "
            f"{self.GECERLI_TCKN}, Telefon: 0546 000 00 90) beyanda "
            "bulunmuştur. Hizmet aracının hasarı tespit edilmiş, dosyanın "
            "hukuk birimine gönderilmesine karar verilmiştir.\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "tutanak"})
        InfoExtractionAgent().run(state)
        LegislationAgent().run(state)
        assert "kvkk_6698" in self._mevzuat_doc_idleri(state)[:3]
        assert state.legislation_meta.get("kvkk_veri_sinyali") is True

    def test_iban_da_tetikler(self):
        metin = (
            "DİLEKÇE\nMükerrer tahsil edilen su faturasının iadesini talep "
            f"ederim. IBAN: {self.ORNEK_IBAN}. Gereğini arz ederim.\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "dilekce"})
        InfoExtractionAgent().run(state)
        LegislationAgent().run(state)
        assert "kvkk_6698" in self._mevzuat_doc_idleri(state)[:3]

    def test_pii_yoksa_enjeksiyon_yok(self):
        metin = (
            "T.C.\nAKÇOVA BELEDİYE BAŞKANLIĞI\nBütçe uygulama genelgesi; "
            "ödenek ve harcama tedbirleri hakkındadır. Dağıtım: Tüm birimler.\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "genelge"})
        InfoExtractionAgent().run(state)
        LegislationAgent().run(state)
        assert state.legislation_meta.get("kvkk_veri_sinyali") is False
        # kvkk_6698 yalnızca gerçek tema/metin eşleşmesiyle gelebilir; sinyalle
        # zorla eklenmemiştir
        for m in state.legislation_matches:
            if m.get("doc_id") == "kvkk_6698":
                assert m.get("eklenme_nedeni") != "kvkk_veri_sinyali"

    def test_usul_mevzuati_sifir_sirada_korunur(self):
        """Dilekçede TCKN olsa da usul mevzuatı (3071) ilk sırada kalmalı."""
        metin = (
            "DİLEKÇE\nBaşvuru sahibi Ayşe YILDIZ (T.C. Kimlik No: "
            f"{self.GECERLI_TCKN}). Mükerrer su faturası iadesini talep "
            "ederim. Adres: Liman Mah. No: 5 Kavakdüzü. Arz ederim.\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "dilekce"})
        InfoExtractionAgent().run(state)
        LegislationAgent().run(state)
        assert state.legislation_matches[0].get("doc_id") == "dilekce_hakki_kanunu_3071"
        assert "kvkk_6698" in self._mevzuat_doc_idleri(state)[:3]

    def test_enjekte_edilen_6698_taslak_esiginin_altinda(self):
        """Sinyalle eklenen 6698 benzerliği taslak atıf eşiğinin (0.6) altında
        olmalı (taslak alıntısını zorlamaz) ve şeffaf işaretlenmeli."""
        metin = (
            "TUTANAK\nSürücü (T.C. Kimlik No: "
            f"{self.GECERLI_TCKN}) beyanda bulunmuştur. Zarar tespit edildi.\n"
        )
        state = AgentState(raw_text=metin, classification={"tur": "tutanak"})
        InfoExtractionAgent().run(state)
        LegislationAgent().run(state)
        kvkk = next(
            (m for m in state.legislation_matches if m.get("doc_id") == "kvkk_6698"),
            None,
        )
        assert kvkk is not None
        if kvkk.get("eklenme_nedeni") == "kvkk_veri_sinyali":
            assert kvkk["benzerlik"] < 0.6
            assert "veri-tespit sinyali" in (kvkk.get("gerekce") or "")
