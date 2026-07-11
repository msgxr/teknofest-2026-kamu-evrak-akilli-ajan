"""
KVKK Anonimleştirme Agent — evrakın kişisel verilerden arındırılmış
paylaşım/arşiv nüshasını üretir.

Kamu pratiğinde bir evrak başka birimle veya kurumla paylaşılırken ya da
arşiv nüshası oluşturulurken içindeki kişisel verilerin amaç dışı
aktarımının önlenmesi gerekir. Dayanak: 6698 sayılı Kişisel Verilerin
Korunması Kanunu (KVKK) md. 4 (amaçla bağlantılı, sınırlı ve ölçülü
işleme) ve md. 8 (kişisel verilerin aktarılma şartları). Bu agent,
metindeki kişisel verileri FORMAT KORUYAN ve GERİ DÖNDÜRÜLEMEZ biçimde
maskeler; kurum adları ile unvanlar tüzel kişi / görev bilgisi olduğu
için kişisel veri sayılmaz ve maskelenmez (KVKK yalnızca gerçek kişilere
ilişkin verileri korur).

Maskeleme kuralları:
    - T.C. Kimlik No (resmî checksum ile doğrulanır): "4**********"
      (geçersiz 11 haneli sayılar kimlik değildir, dokunulmaz)
    - Telefon: ilk 2 hane açık kalır → "05** *** ** **"
    - E-posta: yerel kısmın ilk harfi + "***" + alan adı → "n***@ornek.gov.tr"
      (alan adı kurumu gösterir, kişisel veri değildir)
    - IBAN: "TR" + yıldızlar, son 4 hane açık → mutabakat için yeterli,
      hesabı ifşa etmez (ödeme sistemlerindeki yaygın maskeleme pratiği)
    - Kişi adları: baş harfler açık → "E*** K***" (Dr./Prof. gibi unvan
      önekleri korunur; unvan kişisel veri değildir)
    - Adres satırları (mahalle/cadde/sokak + kapı numarası içeren):
      sokak/kapı bölümü "[ADRES MASKELENDİ]" ile değiştirilir; il/ilçe
      düzeyi istatistik/yetki tespiti için kalabilir (tek başına kişiyi
      belirlemez).

Kaynaklar: state.extracted_info (öncelikli: tc_kimlik, telefon, eposta,
iban, kisi_adlari) + agent'ın kendi regex geçişleri; extracted_info boş
olsa da agent bağımsız çalışır. Kimlik checksum'u ve iletişim desenleri,
çıkarım ile maskeleme arasında tutarlılık (tek doğruluk kaynağı) için
info_extraction_agent modülünden alınır.

Şartname Referansı (Görev 1 / Yenilikçilik):
    "İçerikte geçen önemli bilgi unsurlarını çıkarma" adımının KVKK
    uyumlu tamamlayıcısı — tespit edilen kişisel unsurların paylaşım
    nüshasında maskelenmesi.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

# Tek doğruluk kaynağı: çıkarımın bulduğu her unsuru maskeleyebilmek için
# aynı desenler/doğrulama kullanılır (desen ayrışması veri sızıntısı yaratır).
from src.agents.info_extraction_agent import (
    _EPOSTA,
    _IBAN,
    _TC_ADAY,
    _TELEFON,
    _tc_kimlik_gecerli,
)
from src.utils.turkish_nlp import turkish_lower

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.anonimlestirme")

# ----------------------------------------------------------------------
# Sabitler ve derlenmiş desenler
# ----------------------------------------------------------------------

ADRES_MASKESI = "[ADRES MASKELENDİ]"

# Adres satırı: mahalle/cadde/sokak/bulvar sözcüğü VE kapı numarası
# ("No: 14/3") birlikte geçen bölüm. `[^:\n]*?` öneki, "Adres :" gibi
# alan etiketlerinin maskeye dahil edilmesini engeller (etiket korunur);
# kapı numarasından SONRAKİ il/ilçe bölümü maske dışında kalır.
_ADRES_DESENI = re.compile(
    r"[A-ZÇĞİÖŞÜ0-9][^:\n]*?"
    r"(?:Mahalle(?:si)?|Mah\.|Cadde(?:si)?|Cad\.|Sokak|Sokağı|Sok\.|"
    r"Bulvar(?:ı)?|Blv\.)"
    r"[^\n]*?\bNo\s*[:.]?\s*[\dA-Za-z/\-]+"
)

# Kişi adı kaynakları (extracted_info boşken bağımsız çalışma için):
# "Ad Soyad :" alan satırları, "Sayın Ad Soyad" hitapları, numaralı
# katılımcı listeleri ("1. Yakup SARAÇ - Üye") ve imza satırları
# ("Yakup SARAÇ (imzalıdır)"). Resmî yazışma pratiğinde soyadı çoğunlukla
# BÜYÜK harfle yazıldığından devam sözcükleri tümü-büyük olabilir; ilk
# sözcük karışık yazım ister ki tümü-büyük başlık/gündem satırları
# ("MUAYENE VE KABUL ...") kişi adı sanılmasın.
# İsim sözcükleri arasında yalnızca boşluk/sekme kabul edilir (satır
# sonunu aşan eşleşme, hitap altındaki kurum satırını isme katardı).
_UNVAN_ON_EKI = r"(?:(?:Dr|Prof|Doç|Av|Uzm|Öğr|Gör)\.[ \t]*)*"
_ISIM_ILK = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+"
_ISIM_DEVAM = r"(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+|[A-ZÇĞİÖŞÜ]{2,})"
_ISIM_GOVDE = _UNVAN_ON_EKI + _ISIM_ILK + r"(?:[ \t]+" + _ISIM_DEVAM + r"){1,2}"
_AD_SOYAD_ALANI = re.compile(r"Ad[ıi]?\s*[-/ ]?\s*Soyad[ıi]?\s*:\s*(.+)")
_SAYIN_KISI = re.compile(r"Say[ıi]n[ \t]+(" + _ISIM_GOVDE + r")\b")
# Numaralı liste satırı: "1. Ad SOYAD - unvan/kurum" (ayraç zorunludur;
# "1. Fotokopi kağıdı ..." gibi madde satırları isim biçimine uymaz)
_LISTE_KISI = re.compile(
    r"^\s*\d+[.)\-]\s*(" + _ISIM_GOVDE + r")\s*[-–—,(]", re.MULTILINE
)
# İmza satırı: yalnızca isim + "(imzalıdır)"/"(e-imzalıdır)" ya da imza
# çizgisi içeren satırlar (işaret zorunludur; serbest metin kapsanmaz)
_IMZA_ISARETI = r"\(e?-?imzal[ıi]d[ıi]r\)"
_IMZA_KISI = re.compile(
    r"^\s*(" + _ISIM_GOVDE + r")\s*(?:" + _IMZA_ISARETI + r"|_{3,})\s*$",
    re.MULTILINE,
)
# İmza bloğu: tek başına isimden oluşan satır; kişi sayılması için bir
# SONRAKİ satırın unvan taşıması ya da imza işareti içermesi gerekir
# (resmî yazışmada imza bloğu "Ad SOYAD / unvan" düzenindedir).
_IMZA_BLOK_ISIM = re.compile(r"^\s*(" + _ISIM_GOVDE + r")\s*$")
_IMZA_ISARETI_DESENI = re.compile(_IMZA_ISARETI)

# İmza bloğu doğrulaması için unvan ipuçları (isim satırının altındaki
# görev satırında aranır; turkish_lower uygulanmış gövde araması)
_UNVAN_IPUCLARI = (
    "müdür", "başkan", "uzman", "müsteşar", "şef", "memur", "vali",
    "kaymakam", "müşavir", "mühendis", "sekreter", "koordinatör",
    "sorumlu", "yönetici", "amiri", "sayman", "personel",
)

# Maskede korunacak unvan önekleri (kişisel veri değildir; nokta ile veya
# noktasız yazılabilir: "Dr." / "Dr")
_UNVAN_ONEKLERI = {"dr", "prof", "doç", "av", "uzm", "öğr", "gör"}

# Kişi adı adaylarını elemek için kurum/mekân ipuçları (gövde araması;
# ekli biçimleri de yakalar: "müdürlüğüne", "belediyesi" ...). Kurum ve
# birim adları tüzel kişidir, maskelenmez.
_KURUM_IPUCLARI = (
    "müdürlü", "başkanlı", "bakanlı", "valili", "kaymakaml", "belediye",
    "üniversite", "rektörlü", "daire", "kurum", "kurul", "müşavirli",
    "enstitü", "ajans", "mahalle", "cadde", "sokak", "bulvar", "genel",
    "şube", "birim", "komisyon",
)

# İsim görünümlü ama tür adı (cins isim) olan sözcükler: "Halk Günü",
# "Çevre Haftası", "Kalite Toplantısı" gibi etkinlik/kavram adları kişi
# adı değildir. Sözcük BİREBİR karşılaştırılır (gövde araması "Akgün",
# "Ergün" gibi gerçek soyadlarını yanlışlıkla elerdi).
_GENEL_AD_SOZCUKLERI = {
    "günü", "gün", "haftası", "hafta", "ayı", "yılı", "dönemi",
    "toplantı", "toplantısı", "gündem", "gündemi", "salonu", "merkezi",
    "uygulama", "uygulaması", "program", "programı", "proje", "projesi",
    "rapor", "raporu", "plan", "planı", "liste", "listesi", "sistem",
    "sistemi", "hizmet", "hizmetleri", "kültür", "eğitim", "eğitimi",
}

# Tek başına makam/görev bildiren sözcükler ("Sayın Vali Yardımcısı"):
# görev unvanı kişisel veri değildir, bu adaylar maskelenmez.
_MAKAM_SOZCUKLERI = {
    "vali", "valisi", "kaymakam", "kaymakamı", "müdür", "müdürü",
    "başkan", "başkanı", "uzman", "uzmanı", "memur", "memuru",
    "şef", "şefi", "yardımcı", "yardımcısı", "sekreter", "sekreteri",
    "koordinatör", "koordinatörü", "müsteşar", "müsteşarı",
    "mühendis", "mühendisi", "amiri", "sorumlusu", "yetkilisi",
    "müşavir", "müşaviri", "sayman", "saymanı", "vekili",
}


# ----------------------------------------------------------------------
# Maske üretim yardımcıları (format koruyan, geri döndürülemez)
# ----------------------------------------------------------------------

def _tc_maskesi(numara: str) -> str:
    """İlk hane açık, kalan 10 hane yıldız: '27481596372' → '2**********'."""
    return numara[0] + "*" * (len(numara) - 1)


def _telefon_maskesi(telefon: str) -> str:
    """
    İlk 2 hane açık, kalan haneler yıldız; ayraç/boşluk düzeni korunur.

    '0555 314 78 26' → '05** *** ** **'
    """
    sonuc = []
    acik_hane = 0
    for karakter in telefon:
        if karakter.isdigit():
            if acik_hane < 2:
                sonuc.append(karakter)
                acik_hane += 1
            else:
                sonuc.append("*")
        else:
            sonuc.append(karakter)
    return "".join(sonuc)


def _eposta_maskesi(eposta: str) -> str:
    """Yerel kısmın ilk harfi + '***' + alan adı: 'n***@ornek.gov.tr'."""
    yerel, _, alan = eposta.partition("@")
    if not yerel or not alan:
        return "***"
    return yerel[0] + "***@" + alan


def _iban_maskesi(iban: str) -> str:
    """
    'TR' öneki ve son 4 hane açık, kalan haneler yıldız; boşluk düzeni korunur.

    'TR33 0006 ... 8413 26' → 'TR** **** ... **13 26'
    """
    hane_konumlari = [i for i, ch in enumerate(iban) if ch.isdigit()]
    acik_konumlar = set(hane_konumlari[-4:])
    sonuc = []
    for i, karakter in enumerate(iban):
        if karakter.isdigit() and i not in acik_konumlar:
            sonuc.append("*")
        else:
            sonuc.append(karakter)
    return "".join(sonuc)


def _kisi_adi_maskesi(ad: str) -> str:
    """
    Her ad/soyad sözcüğünün baş harfi açık: 'Elif KOÇAK' → 'E*** K***'.

    Unvan önekleri (Dr., Prof. ...) görev/akademik bilgi olduğundan
    olduğu gibi korunur: 'Dr. Mehmet Kaya' → 'Dr. M*** K***'.
    """
    parcalar = []
    for token in ad.split():
        if turkish_lower(token).rstrip(".") in _UNVAN_ONEKLERI:
            parcalar.append(token)
        elif token:
            parcalar.append(token[0] + "***")
    return " ".join(parcalar)


class AnonimlestirmeAgent:
    """
    KVKK anonimleştirme agent'ı.

    Evrak metnindeki kişisel verileri (T.C. kimlik, telefon, e-posta,
    IBAN, kişi adı, adres) format koruyan biçimde maskeleyerek
    state.anonymized_text (paylaşım/arşiv nüshası) ve
    state.anonymization_report (maskeleme sayımı) alanlarını üretir.
    Tamamen kural tabanlıdır; çevrimdışı çalışır.
    """

    def __init__(self) -> None:
        logger.info("KVKK Anonimleştirme Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """
        Evrak metnini anonimleştirir.

        state.raw_text esas alınır; state.extracted_info doluysa oradaki
        değerler öncelikli aday listesi olarak kullanılır, boşsa agent
        kendi regex geçişleriyle bağımsız çalışır.
        """
        metin = getattr(state, "raw_text", "") or ""
        extracted = getattr(state, "extracted_info", None) or {}

        sayaclar = {
            "tc_kimlik": 0,
            "telefon": 0,
            "eposta": 0,
            "iban": 0,
            "kisi_adi": 0,
            "adres": 0,
        }

        # Sıra önemlidir: IBAN önce maskelenir ki içindeki hane grupları
        # telefon/kimlik desenlerine yanlış aday oluşturmasın; adresler
        # kişi adlarından önce maskelenir (satır bütünlüğü korunur).
        metin, sayaclar["iban"] = self._iban_maskele(metin)
        metin, sayaclar["tc_kimlik"] = self._tc_maskele(metin)
        metin, sayaclar["telefon"] = self._telefon_maskele(metin)
        metin, sayaclar["eposta"] = self._eposta_maskele(metin)
        metin, sayaclar["adres"] = self._adres_maskele(metin)
        metin, sayaclar["kisi_adi"] = self._kisi_adlarini_maskele(metin, extracted)

        # Güvenlik ağı: çıkarım agent'ının bulduğu ancak yukarıdaki
        # geçişlerden kaçan değerler birebir aranıp maskelenir.
        metin = self._kalan_degerleri_maskele(metin, extracted, sayaclar)

        # Not: bu iki alan AgentState'e orkestratör entegrasyonunda
        # eklenir; doğrudan atama dataclass olmayan durumlarda da çalışır.
        state.anonymized_text = metin
        state.anonymization_report = {
            "maskelenen": sayaclar,
            "toplam": sum(sayaclar.values()),
            "yontem": "kural_tabanli",
        }
        logger.info(
            f"Anonimleştirme tamamlandı: {sum(sayaclar.values())} unsur maskelendi."
        )
        return state

    # ------------------------------------------------------------------
    # Kategori bazlı maskeleme geçişleri
    # ------------------------------------------------------------------

    def _tc_maskele(self, metin: str) -> "tuple[str, int]":
        """Checksum'ı geçerli T.C. Kimlik Numaralarını maskeler."""
        adet = 0

        def degistir(m: "re.Match") -> str:
            nonlocal adet
            numara = m.group(1)
            # Checksum geçmeyen 11 haneli sayılar kimlik değildir
            # (evrak/karar numarası olabilir); dokunulmaz.
            if not _tc_kimlik_gecerli(numara):
                return m.group(0)
            adet += 1
            return _tc_maskesi(numara)

        return _TC_ADAY.sub(degistir, metin), adet

    def _telefon_maskele(self, metin: str) -> "tuple[str, int]":
        """Türkiye biçimli telefon numaralarını maskeler (ilk 2 hane açık)."""
        adet = 0

        def degistir(m: "re.Match") -> str:
            nonlocal adet
            deger = m.group(0)
            hane_sayisi = sum(1 for ch in deger if ch.isdigit())
            if not 10 <= hane_sayisi <= 12:
                return deger
            adet += 1
            return _telefon_maskesi(deger)

        return _TELEFON.sub(degistir, metin), adet

    def _eposta_maskele(self, metin: str) -> "tuple[str, int]":
        """E-posta adreslerini maskeler (alan adı açık kalır)."""
        adet = 0

        def degistir(m: "re.Match") -> str:
            nonlocal adet
            adet += 1
            return _eposta_maskesi(m.group(0))

        return _EPOSTA.sub(degistir, metin), adet

    def _iban_maskele(self, metin: str) -> "tuple[str, int]":
        """IBAN'ları maskeler (son 4 hane açık kalır)."""
        adet = 0

        def degistir(m: "re.Match") -> str:
            nonlocal adet
            adet += 1
            return _iban_maskesi(m.group(0))

        return _IBAN.sub(degistir, metin), adet

    def _adres_maskele(self, metin: str) -> "tuple[str, int]":
        """
        Adres satırlarının sokak/kapı bölümünü maskeler.

        Yalnızca hem yer öğesi (mahalle/cadde/sokak/bulvar) hem kapı
        numarası ("No: 14/3") içeren bölümler maskelenir; gövde metnindeki
        "X Mahallesi'nde ikamet eden" gibi genel anlatımlar (kapı numarası
        yoktur) korunur. Kapı numarasından sonraki il/ilçe bilgisi kalır.
        """
        adet = 0

        def degistir(m: "re.Match") -> str:
            nonlocal adet
            adet += 1
            return ADRES_MASKESI

        return _ADRES_DESENI.sub(degistir, metin), adet

    # ------------------------------------------------------------------
    # Kişi adları
    # ------------------------------------------------------------------

    def _kisi_adlarini_maskele(self, metin: str, extracted: dict) -> "tuple[str, int]":
        """Aday kişi adlarının metindeki tüm geçişlerini maskeler."""
        adet = 0
        for ad in self._kisi_adi_adaylari(metin, extracted):
            maske = _kisi_adi_maskesi(ad)
            desen = re.compile(r"(?<!\w)" + re.escape(ad) + r"(?!\w)")
            metin, n = desen.subn(lambda m: maske, metin)
            adet += n
        return metin, adet

    def _kisi_adi_adaylari(self, metin: str, extracted: dict) -> "list[str]":
        """
        Maskelenecek kişi adı adaylarını toplar.

        Kaynaklar: extracted_info.kisi_adlari (öncelikli), "Ad Soyad :"
        alan satırları, "Sayın Ad Soyad" hitapları, numaralı katılımcı
        listeleri ve imza satırları. Kurum/makam bildiren adaylar elenir
        (tüzel kişi ve görev unvanı maskelenmez). Uzun adaylar önce
        maskelenir ki "Dr. Mehmet Kaya" varken "Mehmet Kaya" parçası
        ayrıca eşleşmesin.
        """
        adaylar = []
        for ad in extracted.get("kisi_adlari") or []:
            if isinstance(ad, str):
                adaylar.append(ad.strip())

        for m in _AD_SOYAD_ALANI.finditer(metin):
            # Parantez/virgül sonrası açıklamalar ada dahil edilmez
            deger = re.split(r"[(,;]", m.group(1))[0].strip()
            adaylar.append(deger)

        for desen in (_SAYIN_KISI, _LISTE_KISI, _IMZA_KISI):
            for m in desen.finditer(metin):
                adaylar.append(m.group(1).strip())

        # İmza bloğu: tek başına isim satırı + altında unvan/imza satırı
        satirlar = metin.split("\n")
        for i, satir in enumerate(satirlar):
            m = _IMZA_BLOK_ISIM.match(satir)
            if not m:
                continue
            sonraki = satirlar[i + 1].strip() if i + 1 < len(satirlar) else ""
            sonraki_tl = turkish_lower(sonraki)
            if any(u in sonraki_tl for u in _UNVAN_IPUCLARI) or _IMZA_ISARETI_DESENI.search(sonraki_tl):
                adaylar.append(m.group(1).strip())

        secilen = []
        gorulen = set()
        for ad in adaylar:
            if not ad or ad in gorulen:
                continue
            gorulen.add(ad)
            if self._kisi_adi_mi(ad):
                secilen.append(ad)
        secilen.sort(key=len, reverse=True)
        return secilen

    @staticmethod
    def _kisi_adi_mi(aday: str) -> bool:
        """
        Adayın gerçek kişi adı olup olmadığını denetler.

        Kurum/mekân ipucu taşıyan, makam sözcüğü içeren ya da tür adı
        (etkinlik/kavram: "Halk Günü") barındıran adaylar kişi adı
        sayılmaz; unvan önekleri düşüldükten sonra en az iki sözcük
        (ad + soyad) kalmalıdır (tek sözcük yaygın kelimelerle çakışıp
        aşırı maskelemeye yol açar).
        """
        tl = turkish_lower(aday)
        if any(ipucu in tl for ipucu in _KURUM_IPUCLARI):
            return False
        tokenlar = [t for t in aday.split() if turkish_lower(t).rstrip(".") not in _UNVAN_ONEKLERI]
        if len(tokenlar) < 2:
            return False
        for token in tokenlar:
            token_tl = turkish_lower(token)
            if token_tl in _MAKAM_SOZCUKLERI or token_tl in _GENEL_AD_SOZCUKLERI:
                return False
        return True

    # ------------------------------------------------------------------
    # Güvenlik ağı: extracted_info değerlerinin birebir maskelenmesi
    # ------------------------------------------------------------------

    def _kalan_degerleri_maskele(self, metin: str, extracted: dict, sayaclar: dict) -> str:
        """
        Regex geçişlerinden kaçan çıkarım değerlerini birebir maskeler.

        Çıkarım agent'ı değerleri normalize edebildiği için (ör. IBAN
        boşluksuz) çoğu değer zaten maskelenmiştir; burada yalnızca
        metinde hâlâ açık duran değerler yakalanır.
        """
        kurallar = (
            ("tc_kimlik", _tc_maskesi, _tc_kimlik_gecerli),
            ("telefon", _telefon_maskesi, None),
            ("eposta", _eposta_maskesi, None),
            ("iban", _iban_maskesi, None),
        )
        for anahtar, maske_uret, dogrula in kurallar:
            for deger in extracted.get(anahtar) or []:
                if not isinstance(deger, str) or not deger.strip():
                    continue
                deger = deger.strip()
                if dogrula is not None and not dogrula(deger):
                    continue
                n = metin.count(deger)
                if n:
                    metin = metin.replace(deger, maske_uret(deger))
                    sayaclar[anahtar] += n
        return metin

