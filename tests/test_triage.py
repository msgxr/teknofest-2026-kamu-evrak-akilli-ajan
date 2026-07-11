"""
Triage (Akıllı Önceliklendirme) Agent testleri.

Tarih hesapları deterministik olsun diye agent'a sabit bir "bugün"
enjekte edilir (TriageAgent(bugun=...)). Takvim gerçekleri:
2026-06-22 Pazartesi, 2026-07-01 Çarşamba, 2026-07-06 Pazartesi.
"""

import sys
from datetime import date
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import AgentState
from src.agents.triage_agent import TriageAgent, is_gunu_ekle


def _state(text, tur="diger", evrak_tarihi="", tarihler=None):
    """Testler için asgari dolulukta AgentState kurar."""
    state = AgentState(raw_text=text)
    state.classification = {"tur": tur, "tur_adi": tur, "guven": 0.9}
    state.extracted_info = {
        "evrak_tarihi": evrak_tarihi,
        "tarihler": tarihler or ([evrak_tarihi] if evrak_tarihi else []),
    }
    state.legislation_matches = []
    return state


class TestTriageAgent:
    """Triage Agent birim testleri."""

    def setup_method(self):
        """Her test öncesi sabit 'bugün' ile agent kur."""
        self.agent = TriageAgent(bugun=date(2026, 7, 1))

    # ------------------------------------------------------------------
    # Katman 1: aciliyet damgaları
    # ------------------------------------------------------------------

    def test_ivedi_damgasi(self):
        """İVEDİ damgalı yazı doğrudan 'ivedi' öncelik almalı."""
        state = _state(
            "T.C.\nAKÇOVA VALİLİĞİ\n\nİVEDİ\n\n"
            "Sayı : E-123\nKonu : Personel görevlendirmesi\n"
            "Gereğini rica ederim."
        )
        result = self.agent.run(state)
        assert result.triage["oncelik"] == "ivedi"
        tipler = [s["tip"] for s in result.triage["sinyaller"]]
        assert "aciliyet_damgasi" in tipler

    def test_cok_ivedi_tek_sinyal(self):
        """ÇOK İVEDİ damgası azami skor üretmeli, yalın İVEDİ ile çift sinyal olmamalı."""
        state = _state("ÇOK İVEDİ\n\nDeprem bölgesine sevkiyat hakkında yazıdır.")
        result = self.agent.run(state)
        assert result.triage["oncelik"] == "ivedi"
        assert result.triage["skor"] == 1.0
        damgalar = [
            s["deger"] for s in result.triage["sinyaller"]
            if s["tip"] == "aciliyet_damgasi"
        ]
        assert damgalar == ["ÇOK İVEDİ"]

    def test_gunludur_damgasi_yuksek(self):
        """GÜNLÜDÜR ibaresi (süreli evrak) en az 'yuksek' öncelik almalı."""
        state = _state("GÜNLÜDÜR\n\nSayı : E-42\nKonu : Veri girişi hakkında.")
        result = self.agent.run(state)
        assert result.triage["oncelik"] in ("yuksek", "ivedi")

    # ------------------------------------------------------------------
    # Katman 2: metin içi süre / açık son tarih
    # ------------------------------------------------------------------

    def test_15_gun_icinde_hesabi(self):
        """'15 gün içinde' evrak tarihine 15 takvim günü eklemeli."""
        state = _state(
            "Söz konusu eksikliklerin 15 gün içinde giderilmesi gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-16"
        assert result.triage["kalan_gun"] == 15
        assert result.triage["oncelik"] == "yuksek"

    def test_is_gunu_hesabi_hafta_sonu_atlar(self):
        """'5 iş günü içinde' hafta sonlarını atlamalı (Pzt 06.07 + 5 iş günü = Pzt 13.07)."""
        state = _state(
            "Raporun 5 iş günü içinde gönderilmesi rica olunur.",
            evrak_tarihi="06.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-13"

    def test_en_gec_acik_tarih(self):
        """'en geç <tarih>' kalıbı evrak tarihi olmasa da son tarih üretmeli."""
        state = _state(
            "Başvuruların en geç 15/08/2026 tarihine kadar iletilmesi gerekmektedir."
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-08-15"
        tipler = [s["tip"] for s in result.triage["sinyaller"]]
        assert "acik_son_tarih" in tipler

    def test_yaziyla_sure(self):
        """Yazıyla verilen süre ('on beş gün içinde') sayıya çevrilmeli."""
        state = _state(
            "Talebin on beş gün içinde sonuçlandırılması gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-16"

    def test_tarihsiz_evrakta_son_tarih_null(self):
        """Evrak tarihi yoksa göreli süre hesaplanamaz: son_tarih null + not."""
        state = _state("Eksikliklerin 30 gün içinde tamamlanması gerekmektedir.")
        result = self.agent.run(state)
        assert result.triage["son_tarih"] is None
        assert result.triage["kalan_gun"] is None
        assert result.triage["not"]

    # ------------------------------------------------------------------
    # Katman 3: yasal süre tablosu
    # ------------------------------------------------------------------

    def test_bilgi_edinme_15_is_gunu(self):
        """Bilgi edinme içeriği 4982 s. Kanun'a göre 15 iş günü süre almalı."""
        state = _state(
            "4982 sayılı Kanun kapsamında bilgi edinme başvurumun "
            "değerlendirilmesini arz ederim.",
            tur="dilekce",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        yasal = result.triage["yasal_sure"]
        assert yasal is not None
        assert yasal["sure_gun"] == 15
        assert yasal["tip"] == "is_gunu"
        assert "4982" in yasal["kaynak"]
        # Çrş 01.07.2026 + 15 iş günü = Çrş 22.07.2026
        # 15 iş günü hesabı 15 Temmuz ulusal tatilini atlar (2429 sayılı Kanun)
        assert result.triage["son_tarih"] == "2026-07-23"

    def test_dilekce_30_gun(self):
        """Dilekçe türü 3071 s. Kanun'a göre 30 takvim günü süre almalı."""
        state = _state(
            "Evimin önündeki yol çalışması hakkında gereğini arz ederim.",
            tur="dilekce",
            evrak_tarihi="22.06.2026",
        )
        result = self.agent.run(state)
        yasal = result.triage["yasal_sure"]
        assert yasal is not None
        assert yasal["sure_gun"] == 30
        assert yasal["tip"] == "takvim"
        assert "3071" in yasal["kaynak"]
        # 30 TAKVİM günü (3071 m.7): tatiller takvim gününü etkilemez
        assert result.triage["son_tarih"] == "2026-07-22"

    # ------------------------------------------------------------------
    # Öncelik / kalan gün davranışı
    # ------------------------------------------------------------------

    def test_normal_evrak(self):
        """Aciliyet ve süre sinyali olmayan evrak 'normal' kalmalı."""
        state = _state(
            "Kurumumuz hizmet binasında yapılan boya çalışması "
            "tamamlanmış olup bilgilerinize sunulur.",
            tur="bilgilendirme",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["oncelik"] == "normal"
        assert result.triage["son_tarih"] is None
        assert result.triage["yasal_sure"] is None

    def test_gecmis_son_tarihte_kalan_gun_negatif(self):
        """Son tarihi geçmiş evrakta kalan_gun negatif olmalı ve öncelik ivediye çıkmalı."""
        agent = TriageAgent(bugun=date(2026, 8, 1))
        state = _state(
            "Cevabın en geç 20/07/2026 tarihine kadar verilmesi gerekmektedir."
        )
        result = agent.run(state)
        assert result.triage["kalan_gun"] == -12
        assert result.triage["oncelik"] == "ivedi"

    def test_yaklasan_sure_eskalasyonu(self):
        """Son tarihe 3 gün ve daha az kala öncelik ivediye yükselmeli."""
        agent = TriageAgent(bugun=date(2026, 7, 14))
        state = _state(
            "Eksikliklerin 15 gün içinde giderilmesi gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = agent.run(state)
        assert result.triage["kalan_gun"] == 2
        assert result.triage["oncelik"] == "ivedi"

    def test_en_erken_son_tarih_secilir(self):
        """Birden fazla süre kaydında en erken tarih bağlayıcı olmalı."""
        state = _state(
            "Taslağın 10 gün içinde, nihai raporun ise en geç "
            "15/08/2026 tarihine kadar gönderilmesi gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-11"


class TestBasvuruNiteligiKosulu:
    """Yasal sürelerin başvuru niteliği ön koşulu (Katman 3 kapsam doğruluğu).

    3071/4982/CİMER cevap süreleri idareye yöneltilmiş bir başvuruyu
    cevaplama yükümlülüğünden doğar; başvuru niteliği olmayan iç belgelere
    (tutanak/rapor/genelge/onaylı belge/bilgilendirme) atanmamalıdır.
    """

    def setup_method(self):
        """Her test öncesi sabit 'bugün' ile agent kur."""
        self.agent = TriageAgent(bugun=date(2026, 7, 1))

    def test_ic_rapor_yasal_sure_almaz(self):
        """CİMER'den söz eden iç istatistik raporu kanuni cevap süresi almamalı."""
        state = _state(
            "CİMER üzerinden kurumumuza iletilen başvuruların aylık "
            "dağılımını gösteren istatistik raporu ekte sunulmuştur.",
            tur="rapor",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["yasal_sure"] is None
        assert result.triage["son_tarih"] is None

    def test_ic_bilgilendirme_yasal_sure_almaz(self):
        """Başvuru içermeyen iç bilgilendirme yazısına yasal süre atanmamalı."""
        state = _state(
            "İlçemizde etkili olan kar yağışı nedeniyle ana arterlerde kar "
            "küreme ve tuzlama çalışması yapılmıştır. Bilgilerinize sunulur.",
            tur="bilgilendirme",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["yasal_sure"] is None
        assert result.triage["oncelik"] == "normal"

    def test_mevzuat_eslesmesi_ic_belgeye_sure_atamaz(self):
        """Yüksek benzerlikli mevzuat eşleşmesi bile iç belgeye kanuni süre atamamalı."""
        state = _state(
            "Park ve bahçelerde mevsimlik bakım çalışması tamamlanmıştır. "
            "Bilgilerinize sunulur.",
            tur="bilgilendirme",
            evrak_tarihi="01.07.2026",
        )
        state.legislation_matches = [
            {
                "baslik": "CİMER ve Vatandaş Başvuruları Hakkında Bilgi Notu",
                "benzerlik": 0.9,
            }
        ]
        result = self.agent.run(state)
        assert result.triage["yasal_sure"] is None

    def test_genelge_bilgi_edinme_konulu_sure_almaz(self):
        """Bilgi edinme USULÜNÜ düzenleyen genelge 15 iş günü süresi almamalı."""
        state = _state(
            "Bilgi edinme başvurularının birimlerce cevaplanmasında uyulacak "
            "usul ve esaslar aşağıda belirtilmiştir.",
            tur="genelge",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["yasal_sure"] is None

    def test_dilekce_3071_suresi_korunur(self):
        """Dilekçe türü başvuru niteliği taşır: 3071 m.7 30 gün süresi işlemeli."""
        state = _state(
            "Mahallemizdeki park aydınlatmasının onarılması hususunda "
            "gereğini arz ederim.",
            tur="dilekce",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        yasal = result.triage["yasal_sure"]
        assert yasal is not None
        assert yasal["sure_gun"] == 30
        assert "3071" in yasal["kaynak"]
        assert result.triage["son_tarih"] == "2026-07-31"

    def test_cimer_havale_ust_yazisi_sure_alir(self):
        """Başvuru içeren CİMER havale üst yazısı 30 günlük takibe girmeli."""
        state = _state(
            "CİMER üzerinden Başkanlığımıza iletilen başvuruda, vatandaş "
            "mahallesindeki yol bozukluğunun giderilmesini talep etmektedir. "
            "Gereğini rica ederim.",
            tur="ust_yazi",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        yasal = result.triage["yasal_sure"]
        assert yasal is not None
        assert yasal["sure_gun"] == 30
        assert "CİMER" in yasal["kaynak"]

    def test_metin_ici_sure_ic_yazida_calisir(self):
        """Metin içi açık süre kaydı ('10 gün içinde') iç yazıda da çalışmalı."""
        state = _state(
            "Denetimde tespit edilen hususların 10 gün içinde giderilerek "
            "sonucundan bilgi verilmesi gerekmektedir.",
            tur="rapor",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["yasal_sure"] is None
        assert result.triage["son_tarih"] == "2026-07-11"
        tipler = [s["tip"] for s in result.triage["sinyaller"]]
        assert "metin_ici_sure" in tipler


class TestYardimcilar:
    """Yardımcı fonksiyon testleri."""

    def test_is_gunu_ekle_hafta_sonu(self):
        """Cuma + 1 iş günü = Pazartesi (2026-07-03 Cuma)."""
        assert is_gunu_ekle(date(2026, 7, 3), 1) == date(2026, 7, 6)

    def test_is_gunu_ekle_uzun(self):
        """Çarşamba 01.07 + 15 iş günü = Çarşamba 22.07."""
        # 15 Temmuz (Demokrasi ve Millî Birlik Günü) tatili atlanır
        assert is_gunu_ekle(date(2026, 7, 1), 15) == date(2026, 7, 23)


class TestResmiTatilHesabi:
    """İş günü hesabında resmî tatil kenar durumları (P0-4 sertifikasyon).

    Dayanaklar: 4982 m.11 (15 iş günü), 2429 sayılı Kanun (ulusal
    bayram/genel tatiller). Sabit ulusal tatiller otomatik atlanır;
    yıla özgü dinî bayramlar parametrik `resmi_tatiller` ile verilir.
    """

    def test_sabit_ulusal_tatil_atlanir(self):
        """14 Tem 2026 Salı + 1 iş günü: 15 Temmuz tatili atlanmalı → 16 Per."""
        assert is_gunu_ekle(date(2026, 7, 14), 1) == date(2026, 7, 16)

    def test_tatil_hafta_sonu_kombinasyonu(self):
        """28 Ağu 2026 Cuma + 1 iş günü: hafta sonu + 30 Ağu Pzt (Zafer
        Bayramı da pazara denk 2026'da → 30 Ağu Pazar zaten hafta sonu)
        → 31 Ağu Pazartesi."""
        assert is_gunu_ekle(date(2026, 8, 28), 1) == date(2026, 8, 31)

    def test_yilbasi_ve_yil_gecisi(self):
        """31 Ara 2026 Per + 1 iş günü: 1 Oca 2027 Cuma tatil, hafta sonu
        atlanır → 4 Oca 2027 Pazartesi."""
        assert is_gunu_ekle(date(2026, 12, 31), 1) == date(2027, 1, 4)

    def test_parametrik_dini_bayram_atlanir(self):
        """Kurumca verilen tam tarihli ek tatil (kurgu bayram günü) atlanmalı."""
        ek = {date(2026, 7, 13)}  # Pazartesi (kurgu ek tatil)
        # 10 Tem Cuma → 11-12 hafta sonu + 13 ek tatil atlanır → 14 Salı
        assert is_gunu_ekle(date(2026, 7, 10), 1, ek) == date(2026, 7, 14)
        # Bileşik durum: +2 iş günü → 15 Tem SABİT tatili de atlanır → 16 Per
        assert is_gunu_ekle(date(2026, 7, 10), 2, ek) == date(2026, 7, 16)

    def test_parametrik_tatil_agent_uzerinden(self):
        """TriageAgent resmi_tatiller parametresi iş günü hesabına yansımalı."""
        metin = (
            "T.C. KURGU KURUMU\n"
            "Tarih : 10.07.2026\n"
            "Konu : Bilgi edinme başvurusu hk.\n\n"
            "4982 sayılı Bilgi Edinme Hakkı Kanunu kapsamında başvurumun "
            "cevaplanmasını arz ederim.\n"
        )
        state = AgentState(raw_text=metin)
        state.classification = {"tur": "dilekce", "guven": 0.9}
        state.extracted_info = {"tarih": "10.07.2026"}

        tatilsiz = TriageAgent(bugun=date(2026, 7, 10)).run(
            AgentState(raw_text=metin, classification={"tur": "dilekce"},
                       extracted_info={"tarih": "10.07.2026"})
        ).triage
        ek_tatilli = TriageAgent(
            bugun=date(2026, 7, 10),
            resmi_tatiller={date(2026, 7, 20), date(2026, 7, 21)},
        ).run(state).triage

        t1 = tatilsiz.get("son_tarih")
        t2 = ek_tatilli.get("son_tarih")
        assert t1 and t2, "Yasal süreden son işlem tarihi hesaplanmalı"
        # İki ek tatil iş günü hesabını en az bir gün ileri atmalı
        assert t2 > t1
