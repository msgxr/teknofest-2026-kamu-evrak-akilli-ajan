"""
KVKK Anonimleştirme Agent testleri.

6698 sayılı KVKK bağlamındaki maskeleme kurallarını doğrular:
her kişisel veri türünün format koruyan maskesi, geçersiz (checksum
tutmayan) T.C. kimlik adaylarının korunması, kurum adları ile unvanların
maskelenMEmesi ve boş metin davranışı.
"""

import sys
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.anonimlestirme_agent import AnonimlestirmeAgent


class SahteState:
    """
    Anonimleştirme için gereken alanları taşıyan mini durum nesnesi.

    AgentState'e ana oturumda eklenecek anonymized_text /
    anonymization_report alanları çalışma anında atanabildiği için
    dataclass olmayan bu sahte sınıf yeterlidir.
    """

    def __init__(self, raw_text="", extracted_info=None):
        self.raw_text = raw_text
        self.extracted_info = extracted_info or {}


class TestAnonimlestirmeAgent:
    """KVKK Anonimleştirme Agent birim testleri."""

    def setup_method(self):
        """Her test öncesi agent'ı başlat."""
        self.agent = AnonimlestirmeAgent()

    # ------------------------------------------------------------------
    # T.C. Kimlik Numarası
    # ------------------------------------------------------------------

    def test_tc_kimlik_maskeleme(self):
        """Checksum'ı geçerli T.C. kimlik ilk hane açık maskelenmeli."""
        state = SahteState(raw_text="T.C. Kimlik No : 10000000146")
        result = self.agent.run(state)
        assert "10000000146" not in result.anonymized_text
        assert "1**********" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["tc_kimlik"] == 1

    def test_gecersiz_tc_maskelenmez(self):
        """Checksum'ı geçersiz 11 haneli sayı kimlik değildir, korunmalı."""
        state = SahteState(raw_text="Başvuru No : 12345678901 sayılı kayıt")
        result = self.agent.run(state)
        assert "12345678901" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["tc_kimlik"] == 0

    # ------------------------------------------------------------------
    # Telefon / e-posta / IBAN
    # ------------------------------------------------------------------

    def test_telefon_maskeleme(self):
        """Telefonun ilk 2 hanesi açık kalmalı, düzen korunmalı."""
        state = SahteState(raw_text="Telefon : 0555 000 00 01")
        result = self.agent.run(state)
        assert "0555 000 00 01" not in result.anonymized_text
        assert "05** *** ** **" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["telefon"] == 1

    def test_eposta_maskeleme(self):
        """E-postada yerel kısım maskelenmeli, alan adı açık kalmalı."""
        state = SahteState(raw_text="E-posta : nur.yilmaz@ornek.gov.tr")
        result = self.agent.run(state)
        assert "nur.yilmaz@ornek.gov.tr" not in result.anonymized_text
        assert "n***@ornek.gov.tr" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["eposta"] == 1

    def test_iban_maskeleme(self):
        """IBAN'da yalnızca son 4 hane açık kalmalı, boşluk düzeni korunmalı."""
        state = SahteState(raw_text="IBAN : TR33 0006 1005 1978 6457 8413 26")
        result = self.agent.run(state)
        assert "0006" not in result.anonymized_text
        assert "TR** **** **** **** **** **13 26" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["iban"] == 1

    def test_dogum_tarihi_maskeleme(self):
        """'Doğum Tarihi' etiketli tarih maskelenmeli; etiket korunmalı."""
        state = SahteState(raw_text="Doğum Tarihi : 12.01.1990")
        result = self.agent.run(state)
        assert "12.01.1990" not in result.anonymized_text
        assert "Doğum Tarihi" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["dogum_tarihi"] == 1

    def test_olagan_evrak_tarihi_maskelenmez(self):
        """Etiketsiz evrak/yazı tarihi maskelenmemeli (aşırı maskeleme yok)."""
        state = SahteState(raw_text="Tarih : 12.01.1990\nToplantı 15.03.2026 tarihinde yapılacaktır.")
        result = self.agent.run(state)
        assert "12.01.1990" in result.anonymized_text
        assert "15.03.2026" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["dogum_tarihi"] == 0

    def test_sicil_no_maskeleme(self):
        """'Sicil No' etiketli sicil numarası maskelenmeli (ilk hane açık)."""
        state = SahteState(raw_text="Sicil No : 123456")
        result = self.agent.run(state)
        assert "123456" not in result.anonymized_text
        assert "1*****" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["sicil_no"] == 1

    def test_evrak_karar_no_maskelenmez(self):
        """Esas/Karar/Evrak numaraları sicil değildir; maskelenmemeli."""
        state = SahteState(raw_text="Karar No : 2026/145\nEsas No : 2026/98")
        result = self.agent.run(state)
        assert "2026/145" in result.anonymized_text
        assert "2026/98" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["sicil_no"] == 0

    def test_dogum_tarihi_tire_ve_iso_maskeleme(self):
        """Tire ayraçlı ve ISO biçimli doğum tarihleri de maskelenmeli."""
        for metin in ("Doğum Tarihi : 12-01-1990", "Doğum Tarihi: 1990-01-12"):
            result = self.agent.run(SahteState(raw_text=metin))
            assert "1990" not in result.anonymized_text, metin
            assert result.anonymization_report["maskelenen"]["dogum_tarihi"] == 1, metin

    def test_ayracli_sicil_kuyrugu_sizmaz(self):
        """Boşluk/tire ayraçlı sicilde ilk hane hariç TÜM haneler maskelenmeli."""
        result = self.agent.run(SahteState(raw_text="Sicil No : 123 456"))
        # Son blok '456' açıkta kalmamalı
        assert "456" not in result.anonymized_text
        assert "1** ***" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["sicil_no"] == 1

    def test_tuzel_kisi_sicili_maskelenmez(self):
        """Ticaret/Vergi/Tapu sicili tüzel kişi verisidir; maskelenmemeli (KVKK)."""
        for metin in ("Ticaret Sicil No : 1234567", "Vergi Sicil No: 9876543210"):
            result = self.agent.run(SahteState(raw_text=metin))
            assert "1234567" in result.anonymized_text or "9876543210" in result.anonymized_text
            assert result.anonymization_report["maskelenen"]["sicil_no"] == 0, metin

    # ------------------------------------------------------------------
    # Kişi adları
    # ------------------------------------------------------------------

    def test_kisi_adi_extracted_kaynagindan(self):
        """extracted_info.kisi_adlari'ndaki ad baş harfler kalarak maskelenmeli."""
        state = SahteState(
            raw_text="Toplantıya Mehmet Kaya katılmıştır.",
            extracted_info={"kisi_adlari": ["Mehmet Kaya"]},
        )
        result = self.agent.run(state)
        assert "Mehmet Kaya" not in result.anonymized_text
        assert "M*** K***" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 1

    def test_kisi_adi_ad_soyad_satirindan_bagimsiz(self):
        """extracted_info boşken 'Ad Soyad :' satırından bağımsız maskelemeli."""
        state = SahteState(raw_text="Ad Soyad : Elif KOÇAK\nİmza : (imzalıdır)")
        result = self.agent.run(state)
        assert "Elif KOÇAK" not in result.anonymized_text
        assert "Ad Soyad : E*** K***" in result.anonymized_text

    def test_unvan_oneki_korunur(self):
        """Dr./Prof. gibi unvan önekleri maskelenmemeli (kişisel veri değil)."""
        state = SahteState(
            raw_text="Sayın Dr. Mehmet Kaya toplantıya başkanlık etmiştir.",
        )
        result = self.agent.run(state)
        assert "Mehmet Kaya" not in result.anonymized_text
        assert "Dr. M*** K***" in result.anonymized_text

    def test_katilimci_listesi_ve_imza_satiri(self):
        """Tutanak katılımcı listesi ve imza satırındaki adlar maskelenmeli."""
        state = SahteState(
            raw_text=(
                "Komisyon Üyeleri:\n"
                "1. Yakup SARAÇ - Komisyon Başkanı\n"
                "2. Emine ÇAKIROĞLU - Üye\n\n"
                "İmzalar:\n"
                "Yakup SARAÇ (imzalıdır)\n"
            )
        )
        result = self.agent.run(state)
        assert "SARAÇ" not in result.anonymized_text
        assert "ÇAKIROĞLU" not in result.anonymized_text
        assert "1. Y*** S*** - Komisyon Başkanı" in result.anonymized_text
        assert "Y*** S*** (imzalıdır)" in result.anonymized_text

    def test_imza_blogu_unvan_satirindan_taninir(self):
        """İmza bloğundaki 'Ad SOYAD / unvan' düzeni maskelenmeli."""
        state = SahteState(
            raw_text="Bilgilerinizi rica ederim.\n\n"
                     "Selin AYDOĞAN\nİnsan Kaynakları Müdürü\n(e-imzalıdır)\n"
        )
        result = self.agent.run(state)
        assert "AYDOĞAN" not in result.anonymized_text
        assert "S*** A***" in result.anonymized_text
        assert "İnsan Kaynakları Müdürü" in result.anonymized_text  # unvan kalır

    def test_sayin_hitabi_satir_sonunu_asmaz(self):
        """'Sayın Ad SOYAD' altındaki kurum satırı isme katılmamalı."""
        state = SahteState(
            raw_text="Sayın Murat ŞEN\nAraştırma ve Geliştirme Dairesi\n"
        )
        result = self.agent.run(state)
        assert "Sayın M*** Ş***" in result.anonymized_text
        assert "Araştırma ve Geliştirme Dairesi" in result.anonymized_text

    def test_etkinlik_adi_maskelenmez(self):
        """'Halk Günü' gibi etkinlik/kavram adları kişi adı sayılmamalı."""
        state = SahteState(
            raw_text='1. Halk Günü, her ayın ilk çarşamba günü '
                     "konferans salonunda gerçekleştirilecektir.\n"
        )
        result = self.agent.run(state)
        assert result.anonymized_text == state.raw_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    def test_buyuk_harfli_baslik_kisi_sanilmaz(self):
        """Tümü büyük harfli madde/başlık satırları kişi adı sayılmamalı."""
        state = SahteState(
            raw_text="1. MUAYENE VE KABUL - komisyon işlemleri görüşüldü.\n"
                     "1. Fotokopi kağıdı (A4, 80 gr) teslim alındı.\n"
        )
        result = self.agent.run(state)
        assert result.anonymized_text == state.raw_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    # ------------------------------------------------------------------
    # Kişi adı sızıntısı kapatma: serbest metin / etiketli satır /
    # yalın imza satırı (resmî "Ad SOYAD" yazım kuralına dayalı)
    # ------------------------------------------------------------------

    def test_duz_metin_icindeki_ad_soyad_maskelenir(self):
        """Gövde metnindeki resmî 'Ad SOYAD' kalıbı maskelenmeli."""
        state = SahteState(
            raw_text="Başvuru, Fatma Nur DEMİR tarafından teslim edilmiştir."
        )
        result = self.agent.run(state)
        assert "DEMİR" not in result.anonymized_text
        assert "F*** N*** D***" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 1

    def test_hazirlayan_etiketli_satirdaki_ad_maskelenir(self):
        """'Hazırlayan:'/'Teslim Alan:' satırındaki ad maskelenmeli, etiket kalmalı."""
        state = SahteState(
            raw_text="Hazırlayan : Mehmet Ali ÇAKIR\nTeslim Alan : Zeynep KARA\n"
        )
        result = self.agent.run(state)
        assert "ÇAKIR" not in result.anonymized_text
        assert "KARA" not in result.anonymized_text
        assert "Hazırlayan : M*** A*** Ç***" in result.anonymized_text
        assert "Teslim Alan : Z*** K***" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 2

    def test_yalin_imza_satiri_maskelenir(self):
        """Altında unvan olmayan yalın 'Ad SOYAD' imza satırı maskelenmeli."""
        state = SahteState(
            raw_text="Gereğini bilgilerinize arz ederim.\n\nAhmet YILMAZ\n"
        )
        result = self.agent.run(state)
        assert "YILMAZ" not in result.anonymized_text
        assert "A*** Y***" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 1

    def test_yalin_imza_satiri_kucuk_soyadla_maskelenir(self):
        """Kapanış kalıbından sonra 'Ad Soyad' (küçük soyadlı) imza da maskelenmeli."""
        state = SahteState(
            raw_text="Saygılarımla arz ederim.\n\nAhmet Yılmaz\n"
        )
        result = self.agent.run(state)
        assert "Yılmaz" not in result.anonymized_text
        assert "A*** Y***" in result.anonymized_text

    def test_tam_buyuk_kurum_adi_maskelenmez(self):
        """'MİLLİ TEKNOLOJİ BAKANLIĞI' gibi kurum adları maskelenmemeli."""
        metin = (
            "MİLLİ TEKNOLOJİ BAKANLIĞI tarafından yürütülmektedir.\n"
            "Ar-Ge Destekleri Genel MÜDÜRLÜĞÜ konuyu değerlendirmiştir.\n"
        )
        state = SahteState(raw_text=metin)
        result = self.agent.run(state)
        assert result.anonymized_text == metin
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    def test_sayin_tek_kelime_unvan_maskelenmez(self):
        """'Sayın Vali' gibi tek kelimelik makam hitabı maskelenmemeli."""
        metin = "Sayın Vali, programı teşrifleriniz arz olunur.\n"
        state = SahteState(raw_text=metin)
        result = self.agent.run(state)
        assert result.anonymized_text == metin
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    def test_mahalle_cadde_adi_maskelenmez(self):
        """Büyük harfli MAHALLESİ/CADDESİ ekli yer adları maskelenmemeli."""
        metin = (
            "Etkinlik Cumhuriyet CADDESİ ile Yeşiltepe MAHALLESİ "
            "sınırları içinde yapılacaktır.\n"
        )
        state = SahteState(raw_text=metin)
        result = self.agent.run(state)
        assert result.anonymized_text == metin
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    def test_il_adiyla_biten_yer_ifadesi_maskelenmez(self):
        """Adres kuyruğundaki 'İlçe İL' dizisi ('Çankaya ANKARA') maskelenmemeli."""
        metin = "Toplantı, Çankaya ANKARA adresindeki hizmet binasında yapılacaktır.\n"
        state = SahteState(raw_text=metin)
        result = self.agent.run(state)
        assert result.anonymized_text == metin
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    def test_hitap_sozcugu_maske_disinda_kalir(self):
        """Serbest metinde 'Sayın Ahmet YILMAZ' hitabında 'Sayın' açık kalmalı."""
        state = SahteState(
            raw_text="Program, Sayın Ahmet YILMAZ himayelerinde düzenlenecektir."
        )
        result = self.agent.run(state)
        assert "YILMAZ" not in result.anonymized_text
        assert "Sayın A*** Y***" in result.anonymized_text

    # ------------------------------------------------------------------
    # Adres
    # ------------------------------------------------------------------

    def test_adres_maskeleme(self):
        """Sokak/kapı bölümü maskelenmeli, il/ilçe açık kalabilmeli."""
        state = SahteState(
            raw_text="Adres : Yeşiltepe Mahallesi, Ihlamur Caddesi, "
                     "Menekşe Sokak No: 14/3 Doğuşehir"
        )
        result = self.agent.run(state)
        assert "[ADRES MASKELENDİ]" in result.anonymized_text
        assert "Menekşe" not in result.anonymized_text
        assert "Adres :" in result.anonymized_text  # alan etiketi korunur
        assert "Doğuşehir" in result.anonymized_text  # il/ilçe kalır
        assert result.anonymization_report["maskelenen"]["adres"] == 1

    def test_kapi_numarasiz_mahalle_cumlesi_korunur(self):
        """Kapı numarası içermeyen genel anlatım (gövde metni) maskelenmemeli."""
        state = SahteState(
            raw_text="Yeşiltepe Mahallesi'nde ikamet eden vatandaşların talepleri"
        )
        result = self.agent.run(state)
        assert result.anonymized_text == state.raw_text
        assert result.anonymization_report["maskelenen"]["adres"] == 0

    # ------------------------------------------------------------------
    # Kurum adları / boş metin / rapor yapısı
    # ------------------------------------------------------------------

    def test_kurum_adi_korunur(self):
        """Kurum adları tüzel kişidir; hiçbir biçimde maskelenmemeli."""
        metin = (
            "DOĞUŞEHİR BELEDİYE BAŞKANLIĞINA\n"
            "Çevre Koruma Müdürlüğü tarafından hazırlanmıştır.\n"
        )
        state = SahteState(
            raw_text=metin,
            extracted_info={
                "kurum_adlari": ["Doğuşehir Belediye Başkanlığı", "Çevre Koruma Müdürlüğü"],
            },
        )
        result = self.agent.run(state)
        assert "DOĞUŞEHİR BELEDİYE BAŞKANLIĞINA" in result.anonymized_text
        assert "Çevre Koruma Müdürlüğü" in result.anonymized_text
        assert result.anonymization_report["toplam"] == 0

    def test_makam_unvani_maskelenmez(self):
        """'Sayın Vali Yardımcısı' gibi görev unvanları maskelenmemeli."""
        state = SahteState(raw_text="Sayın Vali Yardımcısı imzalamıştır.")
        result = self.agent.run(state)
        assert "Vali Yardımcısı" in result.anonymized_text
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 0

    def test_imza_blogunda_unvan_satiri_maskelenmez(self):
        """İmza bloğunda ad maskelenirken unvan satırı korunmalı."""
        state = SahteState(
            raw_text="Av. Feride SOYLU\nHukuk Müşaviri\n(e-imzalıdır)\n"
        )
        result = self.agent.run(state)
        assert "Av. F*** S***" in result.anonymized_text
        assert "Hukuk Müşaviri" in result.anonymized_text

    def test_bos_metin(self):
        """Boş metinde çıktı boş, sayaçlar sıfır olmalı."""
        state = SahteState(raw_text="")
        result = self.agent.run(state)
        assert result.anonymized_text == ""
        assert result.anonymization_report["toplam"] == 0
        assert result.anonymization_report["yontem"] == "kural_tabanli"

    def test_rapor_yapisi(self):
        """Rapor sözlüğü beklenen anahtar şemasını taşımalı."""
        state = SahteState(raw_text="Ad Soyad : Elif KOÇAK, Tel: 0555 000 00 01")
        result = self.agent.run(state)
        rapor = result.anonymization_report
        assert set(rapor.keys()) == {"maskelenen", "toplam", "yontem"}
        assert set(rapor["maskelenen"].keys()) == {
            "tc_kimlik", "telefon", "eposta", "iban", "kisi_adi", "adres", "plaka",
            "dogum_tarihi", "sicil_no",
        }
        assert rapor["toplam"] == sum(rapor["maskelenen"].values())

    def test_extracted_info_alani_olmayan_state(self):
        """extracted_info alanı hiç olmayan durumda da bağımsız çalışmalı."""

        class YalinState:
            raw_text = "T.C. Kimlik No : 10000000146"

        result = self.agent.run(YalinState())
        assert "1**********" in result.anonymized_text

    def test_coklu_gecis_sayimi(self):
        """Aynı kişisel verinin her geçişi ayrı sayılmalı."""
        state = SahteState(
            raw_text="Elif KOÇAK başvurmuştur. Elif KOÇAK'ın talebi uygundur.",
            extracted_info={"kisi_adlari": ["Elif KOÇAK"]},
        )
        result = self.agent.run(state)
        assert "Elif KOÇAK" not in result.anonymized_text
        assert result.anonymized_text.count("E*** K***") == 2
        assert result.anonymization_report["maskelenen"]["kisi_adi"] == 2
