"""
Bilgi Çıkarım Agent — Evraktan anahtar bilgileri çıkarma.

Regex tabanlı, güvenilir çıkarım esastır; LLM erişilebilirse sonuçlar
`generate_json` ile zenginleştirilir ancak regex sonuçları asla ezilmez.

Çıkarılan unsurlar:
    - tarihler (dd.mm.yyyy, dd/mm/yyyy, "12 Temmuz 2026", ISO)
    - evrak_sayisi (belgenin KENDİ "Sayı :" alanındaki numara; İlgi
      bloğundaki atıf sayıları hariç)
    - referans_numaralari (Sayı : E-12345678-000-1234, EBYS, No: …)
    - tc_kimlik (11 hane + resmi checksum doğrulaması; geçersizler alınmaz)
    - telefon, eposta, iban, para_tutarlari (₺/TL)
    - konu (çok satırlı "Konu :" değeri), muhatap (MAKAMINA/Sayın X)
    - kurum_adlari, kisi_adlari (imza bloğu heuristikleri)
    - dagitim_birimleri ("Dağıtım :" / "Gereği :" / "Bilgi :" satırları;
      bu birimler yazının gönderildiği yerlerdir, kurum_adlari'na katılmaz)
    - ilgi_referanslari ("İlgi :" / "İlgi a)" satırları)

Şartname Referansı (Görev 1):
    "İçerikte geçen önemli bilgi unsurlarını çıkarma"
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.utils.turkish_nlp import turkish_lower

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.info_extraction")

# ----------------------------------------------------------------------
# Derlenmiş desenler (gerçek zamana yakın çalışma için modül seviyesinde)
# ----------------------------------------------------------------------
_AY_ADLARI = (
    r"(?:[Oo]cak|[Şş]ubat|[Mm]art|[Nn]isan|[Mm]ayıs|[Hh]aziran|"
    r"[Tt]emmuz|[Aa]ğustos|[Ee]ylül|[Ee]kim|[Kk]asım|[Aa]ralık)"
)

_TARIH_DESENLERI = [
    re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"),
    re.compile(r"\b\d{1,2}\s+" + _AY_ADLARI + r"\s+\d{4}\b"),
    re.compile(r"\b\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b"),
]

_TARIH_ALANI = re.compile(r"^\s*(?:Toplantı\s+)?Tarih[i]?\s*:\s*(.+)$", re.MULTILINE)

# ----------------------------------------------------------------------
# Evrak tarihi (belgenin kendi tarihi) desenleri
#
# Resmî yazışma kuralı: belgenin kendi tarihi ya "Tarih :" alanında, ya
# "<belge türü> Tarihi :" etiketiyle (Tutanak/Toplantı/Rapor/Onay ...),
# ya sayı satırında, ya da sağ üst / onay bloğunda yalın bir tarih
# satırı ("Ankara, 05.01.2026") olarak yer alır. "İlgi" satırlarındaki
# tarihler ile "... tarihli/tarihinde" kalıbındaki tarihler başka bir
# belgeye/olaya aittir ve evrak tarihi sayılmaz.
# ----------------------------------------------------------------------
# Belgenin kendi tarihini taşıyan alan etiketi (turkish_lower uygulanmış
# satırda aranır). Öneki belge türünü anlatan sözcüklerle sınırlıdır;
# "kesinti/ihale/son başvuru tarihi" gibi olay tarihleri kapsam dışıdır.
_EVRAK_TARIH_ETIKETI = re.compile(
    r"^\s*(?:(?:tutanak|toplantı|rapor|onay|olur|karar|belge|evrak|"
    r"düzenleme|düzenlenme|imza)\s+)?tarih[i]?\s*:"
)
_SAYI_SATIRI = re.compile(r"^\s*say[ıi]\s*:")
# Yalın tarih satırı: isteğe bağlı "Yer adı," öneki + yalnızca tarih
# (dilekçe sağ üstü, onay/olur bloğu tarihi gibi konumlar)
_YALIN_TARIH_SATIRI = re.compile(
    r"^\s*(?:[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü.]*\s*,\s*)?"
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{1,2}\s+" + _AY_ADLARI + r"\s+\d{4})\s*$"
)
# Tarihin hemen ardından gelen "tarihli/tarihinde/tarihleri..." sözcüğü,
# tarihin bu belgeye değil atıf yapılan belgeye/olaya ait olduğunu gösterir.
_ATIF_TARIH_EKI = re.compile(r"^\s*tarihl|^\s*tarihin|^\s*tarihler")
# İSTİSNA — düzenlenme kalıbı: "<tarih> günü/tarihinde ... tanzim
# edilmiştir / düzenlenmiştir / tutulmuştur / imza altına alınmıştır"
# cümlesindeki tarih, belgenin KENDİ düzenlenme tarihidir (tutanak
# kapanış cümlesinin klasik biçimi). turkish_lower uygulanmış, tarihin
# ardından gelen satır parçasında aranır.
_TANZIM_TARIH_EKI = re.compile(
    r"^\s*(?:gün[üu]|tarihinde)\b[^\n]{0,120}?"
    r"(?:tanzim|düzenlen|tutul|kaleme alın|imza altına alın)"
)


def tanzim_tarihi_bul(text: str) -> str:
    """
    "<tarih> günü/tarihinde ... tanzim/düzenlen-/tutul-" kalıbındaki
    düzenlenme tarihini döndürür (yoksa boş dize).

    Tutanak türü belgelerde evrak tarihi çoğunlukla ayrı bir alan yerine
    gövdedeki kapanış cümlesinde verilir; bu yardımcı hem bilgi çıkarımı
    hem eksik bilgi kontrolü tarafından ortak kaynak olarak kullanılır.
    """
    for line in text.split("\n"):
        for pattern in _TARIH_DESENLERI:
            match = pattern.search(line)
            if not match:
                continue
            if pattern is _TARIH_DESENLERI[0]:
                gun, ay = int(match.group(1)), int(match.group(2))
                if not (1 <= gun <= 31 and 1 <= ay <= 12):
                    continue
            if _TANZIM_TARIH_EKI.match(turkish_lower(line[match.end():])):
                return match.group(0)
    return ""


# ----------------------------------------------------------------------
# Sözel (yazıyla) tarih çözümü
#
# Tutanak/olur kapanışlarında tarih rakamsız, tamamen yazıyla verilebilir:
# "İki bin yirmi altı yılı Temmuz ayının on ikinci günü …". Rakamsal tarih
# desenleri bu biçimi kaçırır. Gün adı birler/onlar ve sıra biçimleriyle
# 1-31 aralığında, ay adı ile birleştirilerek çözülür.
# ----------------------------------------------------------------------
_YAZI_GUN_BIRLER = {
    "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4,
    "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9,
}
_YAZI_GUN_BIRLER_SIRA = {
    "birinci": 1, "ikinci": 2, "üçüncü": 3, "ucuncu": 3, "dördüncü": 4,
    "dorduncu": 4, "beşinci": 5, "besinci": 5, "altıncı": 6, "altinci": 6,
    "yedinci": 7, "sekizinci": 8, "dokuzuncu": 9,
}
_YAZI_GUN_ONLAR = {"on": 10, "yirmi": 20, "otuz": 30}
_YAZI_GUN_ONLAR_SIRA = {"onuncu": 10, "yirminci": 20, "otuzuncu": 30}

# "<Ay> ayının <gün-yazı> günü" (turkish_lower uygulanmış metinde aranır)
_SOZEL_TARIH_DESEN = re.compile(
    _AY_ADLARI + r"\s+ayının\s+([a-zçğıöşü]+(?:\s+[a-zçğıöşü]+){0,2})\s+günü"
)


def _yazi_gun_coz(ifade: str):
    """'on ikinci' → 12 gibi yazıyla gün ifadesini 1-31 aralığında çözer.

    Bilinmeyen bir sözcük görülürse (ör. "on ikinci iş") None döner; böylece
    yalnızca gerçek gün ifadeleri tarih üretir.
    """
    toplam = 0
    for w in ifade.split():
        if w in _YAZI_GUN_ONLAR:
            toplam += _YAZI_GUN_ONLAR[w]
        elif w in _YAZI_GUN_ONLAR_SIRA:
            toplam += _YAZI_GUN_ONLAR_SIRA[w]
        elif w in _YAZI_GUN_BIRLER:
            toplam += _YAZI_GUN_BIRLER[w]
        elif w in _YAZI_GUN_BIRLER_SIRA:
            toplam += _YAZI_GUN_BIRLER_SIRA[w]
        else:
            return None
    return toplam if 1 <= toplam <= 31 else None


def _yazi_yil_coz(onceki: str) -> str:
    """Kalıptan önceki metinde yıl arar: rakamsal '20xx' ya da 'iki bin …'
    (2000-2099) biçimi; bulunamazsa boş dize."""
    ry = re.search(r"\b(20\d{2})\b", onceki)
    if ry:
        return ry.group(1)
    idx = onceki.rfind("iki bin")
    if idx < 0:
        return ""
    ek = 0
    for w in onceki[idx + len("iki bin"):].split()[:2]:
        if w in _YAZI_GUN_ONLAR:
            ek += _YAZI_GUN_ONLAR[w]
        elif w in _YAZI_GUN_BIRLER:
            ek += _YAZI_GUN_BIRLER[w]
        else:
            break
    return str(2000 + ek)


def sozel_tarih_bul(text: str) -> str:
    """
    "<Ay> ayının <gün-yazı> günü" kalıbındaki sözel tarihi "GG Ay YYYY"
    (yıl bulunabilirse) biçiminde döndürür; yoksa boş dize.

    Rakamsal tarih içermeyen tutanak/olur belgelerinde evrak tarihinin
    tespiti için kullanılır (rakamsal desenleri tamamlar, ezmez).
    """
    tl = turkish_lower(text)
    m = _SOZEL_TARIH_DESEN.search(tl)
    if not m:
        return ""
    gun = _yazi_gun_coz(m.group(1).strip())
    if gun is None:
        return ""
    ay_adi = tl[m.start():m.end()].split()[0]
    yil = _yazi_yil_coz(tl[max(0, m.start() - 60):m.start()])
    return f"{gun:02d} {ay_adi.capitalize()} {yil}".strip()


_REFERANS_DESENLERI = [
    re.compile(r"^\s*Say[ıi]\s*:\s*([A-Za-z0-9ÇĞİÖŞÜçğıöşü][\w.\-/]*)", re.MULTILINE),
    re.compile(r"\bE-\d{5,}(?:-[\w.]+)*\b"),
    re.compile(r"(?:Evrak|Karar|Kay[ıi]t|Başvuru|Dosya|Belge)\s*No\s*[:.]?\s*([\w.\-/]+)"),
]

# Yalın "No :" deseni ancak belge referansı bağlamında geçerlidir. Adres
# satırlarındaki kapı numaraları ("Sokak No: 21") ile iletişim/kimlik
# satırlarındaki numaralar ("Telefon No :", "T.C. Kimlik No :") evrak
# referansı DEĞİLDİR; eşleşmenin bulunduğu satırın öncesi bu bağlam
# sözcüklerinden birini içeriyorsa aday elenir.
_YALIN_NO = re.compile(r"\bNo\s*:\s*([\w.\-/]+)")
_NO_ADRES_BAGLAMI = re.compile(
    r"\b(?:adres|mahalle|cadde|sokak|sokağ|bulvar|apartman|apt|site|blok|"
    r"kat|daire|kapı|bina|hane|telefon|tel|gsm|faks|kimlik)"
)

_TC_ADAY = re.compile(r"(?<!\d)(\d{11})(?!\d)")

# Türkiye telefon: +90/0 öneki OPSİYONEL (baştaki sıfır olmadan yazılanları da
# yakalar — KVKK sızıntısını kapatır); ilk grup GSM (5xx) veya alan kodu (2xx-4xx)
# ile doğrulanır → rastgele 10 haneli dizilerde aşırı eşleşme sınırlanır ve 11
# haneli TCKN ile çakışmaz. Niceleyiciler RFC sınırlı (CWE-1333 ReDoS'suz).
_TELEFON = re.compile(
    r"(?<!\d)(?:\+90|0)?[\s.\-]?\(?(?:5\d{2}|[2-4]\d{2})\)?"
    r"[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}(?!\d)"
)

# GÜVENLİK (CWE-1333 ReDoS): niceleyiciler RFC sınırlarına bağlandı;
# eski desen ("...+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}") güvenilmeyen uzun metinde
# kuadratik geri izleme yapıyordu (80 KB → ~12 sn). Bu biçim doğrusaldır
# (160 KB → ~40 ms) ve çıktı pariteği korunur.
_EPOSTA = re.compile(r"[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.){1,10}[A-Za-z]{2,24}")

_IBAN = re.compile(r"\bTR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}\b")

_PARA_DESENLERI = [
    re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?\s*(?:TL\b|₺|[Tt]ürk\s+[Ll]irası)"),
    re.compile(r"₺\s*\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?"),
]

_ALAN_SATIRI = re.compile(r"^\s*[\wÇĞİÖŞÜçğıöşü.]{1,25}\s*:")

# İlgi ALAN ETİKETİ: resmî yazışmada "İlgi" bir başlık/alan olarak DAİMA
# iki nokta ile yazılır ("İlgi : a) …", "İlgi: 12.06.2026 tarihli yazı").
# İki nokta ZORUNLUdur — gövde metnindeki "İlgi (b)'de kayıtlı yazınız",
# "İlgi yazı ile", "İlgili eylem planı…" gibi düz cümle atıfları alan
# etiketi DEĞİLDİR ve İlgi bloğu sayılmaz (kopuk İlgi zincirinin yapısal
# tespiti; aksi hâlde var olmayan bir İlgi bloğu "var" sanılır).
_ILGI_SATIRI = re.compile(r"^\s*[İI]lgi\s*:\s*(.*)$")
_ILGI_MADDE = re.compile(r"^\s*([a-zçğıöşü])\)\s*(.+)$")

# Dağıtım bölümü satırları (turkish_lower uygulanmış satırda aranır):
# "Dağıtım :" başlığı ile onu izleyen/serbest "Gereği :" ve "Bilgi :"
# alan satırları. Bu satırlardaki adlar yazının GÖNDERİLDİĞİ birimlerdir
# (dagitim_birimleri); yazıyı üreten kurumun anteti değildir ve
# kurum_adlari alanına karıştırılmaz.
_DAGITIM_BASLIGI = re.compile(r"^\s*dağıtım\s*(?::\s*(.*))?$")
_DAGITIM_ALANI = re.compile(r"^\s*(?:gereği|bilgi)\s*:\s*(.*)$")

_UNVAN_ON_EKI = r"(?:(?:Dr|Prof|Doç|Av|Uzm|Öğr|Gör)\.\s*)*"
_ISIM_GOVDE = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,3}"

_AD_SOYAD_ALANI = re.compile(r"Ad[ıi]?\s*[-/ ]?\s*Soyad[ıi]?\s*:\s*(.+)")
_SAYIN_KISI = re.compile(r"Say[ıi]n\s+(" + _UNVAN_ON_EKI + _ISIM_GOVDE + r")\b")
# Liste satırlarında kişi adı: en fazla 3 kelimelik isim + ayraç (unvan/kurum öncesi)
_LISTE_KISI = re.compile(
    r"^\s*\d+[.)\-]\s*(" + _UNVAN_ON_EKI
    + r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2})\s*[-–—,(]"
)
_IMZA_SATIRI = re.compile(r"^\s*(" + _UNVAN_ON_EKI + _ISIM_GOVDE + r")\s*(_{3,})?\s*$")

# Kişi adı adaylarını elemek için kurum/mekân belirten ekler
_KURUM_TOKENLERI = {
    "müdürlüğü", "müdürlüğüne", "başkanlığı", "başkanlığına", "bakanlığı",
    "bakanlığına", "belediyesi", "üniversitesi", "valiliği", "kaymakamlığı",
    "dairesi", "kurumu", "kurulu", "müşavirliği", "rektörlüğü", "enstitüsü",
    "ajansı", "salonu", "kampüsü", "mahallesi", "caddesi", "sokak", "toplantı",
    "gündem", "tutanak", "ocak", "şubat", "mart", "nisan", "mayıs", "haziran",
    "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık", "sistemi",
    "planı", "raporu", "yönetim",
}

# İmza bloğunda isim doğrulaması için unvan ipuçları (küçük harf)
_UNVAN_IPUCLARI = (
    "müdür", "başkan", "uzman", "müsteşar", "şef", "memur", "vali",
    "kaymakam", "müşavir", "mühendis", "sekreter", "koordinatör",
    "sorumlu", "yönetici", "amiri",
)

_KURUM_EKLERI = (
    "bakanlığı", "müdürlüğü", "başkanlığı", "müşavirliği", "dairesi",
    "kurumu", "kurulu", "ajansı", "enstitüsü", "valiliği", "kaymakamlığı",
    "belediyesi", "üniversitesi", "rektörlüğü", "genel müdürlüğü",
    "daire başkanlığı", "başkanlığı",
)

_KURUM_INLINE = re.compile(
    r"(?:T\.C\.[ \t]+)?((?:[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü.]*[ \t]+){1,5}"
    r"(?:Bakanlığı|Müdürlüğü|Başkanlığı|Müşavirliği|Dairesi|Kurumu|Kurulu|"
    r"Ajansı|Enstitüsü|Valiliği|Kaymakamlığı|Belediyesi|Üniversitesi|Rektörlüğü))"
)


def _tc_kimlik_gecerli(numara: str) -> bool:
    """
    T.C. Kimlik Numarası checksum doğrulaması.

    Kurallar: 11 hane, ilk hane 0 olamaz;
    10. hane = ((1,3,5,7,9. haneler toplamı)*7 - (2,4,6,8. haneler toplamı)) mod 10;
    11. hane = ilk 10 hanenin toplamı mod 10.
    """
    if len(numara) != 11 or not numara.isdigit() or numara[0] == "0":
        return False
    d = [int(c) for c in numara]
    if len(set(d)) == 1:
        return False
    hane10 = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    hane11 = sum(d[:10]) % 10
    return d[9] == hane10 and d[10] == hane11


def _benzersiz(items: list) -> list:
    """Sıralamayı koruyarak yinelenenleri temizler."""
    gorulen = set()
    sonuc = []
    for item in items:
        key = item.strip()
        if key and key not in gorulen:
            gorulen.add(key)
            sonuc.append(key)
    return sonuc


class InfoExtractionAgent:
    """
    Bilgi çıkarım agent'ı.

    Evrak metninden anahtar bilgileri (tarih, kurum, kişi, konu, muhatap,
    referans numarası, iletişim ve mali bilgiler) regex tabanlı çıkarır;
    LLM erişilebilirse sonuçları zenginleştirir (regex sonuçları esastır).
    """

    def __init__(self) -> None:
        logger.info("Bilgi Çıkarım Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evraktan anahtar bilgileri çıkarır ve state.extracted_info'ya yazar."""
        from src.utils.turkce_ner import yer_cikar

        text = state.raw_text

        extracted = {
            "tarihler": self._extract_dates(text),
            "evrak_tarihi": self._extract_document_date(text),
            "kurum_adlari": self._extract_organizations(text),
            "kisi_adlari": self._extract_person_names(text),
            "evrak_sayisi": self._extract_document_number(text),
            "referans_numaralari": self._extract_reference_numbers(text),
            "konu": self._extract_subject(text),
            "muhatap": self._extract_recipient(text),
            "dagitim_birimleri": self._extract_distribution_units(text),
            "tc_kimlik": self._extract_tc_ids(text),
            "telefon": self._extract_phones(text),
            "eposta": _benzersiz(_EPOSTA.findall(text)),
            "iban": self._extract_ibans(text),
            "para_tutarlari": self._extract_amounts(text),
            "ilgi_referanslari": self._extract_ilgi_references(text),
            "yerler": yer_cikar(text),
        }

        # LLM zenginleştirmesi (opsiyonel; regex sonuçları esas alınır)
        self._enrich_with_llm(text, extracted)

        state.extracted_info = extracted
        unsur_sayisi = sum(
            len(v) if isinstance(v, list) else (1 if v else 0) for v in extracted.values()
        )
        logger.info(f"Bilgi çıkarıldı: {unsur_sayisi} unsur")
        return state

    # ------------------------------------------------------------------
    # Tarih / sayı / kimlik / iletişim / mali
    # ------------------------------------------------------------------

    def _extract_dates(self, text: str) -> list:
        """Metinden tarih bilgilerini çıkarır; sayısal tarihleri doğrular."""
        dates = []
        for match in _TARIH_DESENLERI[0].finditer(text):
            gun, ay = int(match.group(1)), int(match.group(2))
            if 1 <= gun <= 31 and 1 <= ay <= 12:
                dates.append(match.group(0))
        for pattern in _TARIH_DESENLERI[1:]:
            dates.extend(m.group(0) for m in pattern.finditer(text))

        # Sözel (yazıyla) tarih — rakamsal tarih içermeyen belgelerde de
        # tarih listesi boş kalmasın (özet/telemetri bu tarihi gösterebilsin)
        sozel = sozel_tarih_bul(text)
        if sozel:
            dates.append(sozel)

        dates = _benzersiz(dates)

        # "Tarih :" alanındaki tarihi (evrak tarihi) listenin başına al
        alan = _TARIH_ALANI.search(text)
        if alan:
            for d in dates:
                if d in alan.group(1):
                    dates.remove(d)
                    dates.insert(0, d)
                    break
        return dates

    @staticmethod
    def _ilgi_blok_satirlari(lines: list) -> set:
        """
        'İlgi' bloğuna ait satır indekslerini döndürür.

        Resmî yazışmada İlgi satırları ve onları izleyen 'a) …', 'b) …'
        madde satırları, atıf yapılan ÖNCEKİ belgelerin tarih/sayısını
        taşır; bu satırlardaki tarihler evrakın kendi tarihi değildir.
        """
        indeksler = set()
        i = 0
        while i < len(lines):
            if _ILGI_SATIRI.match(lines[i]):
                indeksler.add(i)
                j = i + 1
                while j < len(lines) and _ILGI_MADDE.match(lines[j].strip()):
                    indeksler.add(j)
                    j += 1
                i = j
            else:
                i += 1
        return indeksler

    def _extract_document_date(self, text: str) -> str:
        """
        Evrakın KENDİ tarihini çıkarır (atıf tarihlerinden ayrıştırılmış).

        Resmî yazışma yapısına dayanan sinyaller (öncelik sırasıyla):
          1. "Tarih :" veya "<belge türü> Tarihi :" alan satırı,
          2. Sayı satırında yer alan tarih (klasik sayı-tarih düzeni),
          3. Yalın tarih satırı (sağ üst blok, onay/olur bloğu,
             "Yer adı, tarih" biçimi),
          4. Düzenlenme kalıbı: "<tarih> günü/tarihinde ... tanzim
             edilmiştir / düzenlenmiştir / tutulmuştur" (tutanak kapanışı).
        İlgi bloğundaki tarihler ve "… tarihli/tarihinde" kalıbıyla başka
        bir belgeye/olaya bağlanan tarihler evrak tarihi SAYILMAZ.
        """
        lines = text.split("\n")
        ilgi_blok = self._ilgi_blok_satirlari(lines)

        def satirdaki_tarih(line: str) -> str:
            for pattern in _TARIH_DESENLERI:
                match = pattern.search(line)
                if not match:
                    continue
                # Sayısal biçimde gün/ay geçerliliği
                if pattern is _TARIH_DESENLERI[0]:
                    gun, ay = int(match.group(1)), int(match.group(2))
                    if not (1 <= gun <= 31 and 1 <= ay <= 12):
                        continue
                # "… tarihli/tarihinde" kalıbı: atıf tarihi, alma
                kalan = line[match.end():]
                if _ATIF_TARIH_EKI.match(turkish_lower(kalan)):
                    return ""
                return match.group(0)
            return ""

        # 1) "Tarih :" / "<belge türü> Tarihi :" alan satırı
        for i, line in enumerate(lines):
            if i in ilgi_blok:
                continue
            if _EVRAK_TARIH_ETIKETI.match(turkish_lower(line)):
                tarih = satirdaki_tarih(line)
                if tarih:
                    return tarih

        # 2) Sayı satırındaki tarih (klasik "Sayı : … <tarih>" düzeni)
        for i, line in enumerate(lines):
            if i not in ilgi_blok and _SAYI_SATIRI.match(turkish_lower(line)):
                tarih = satirdaki_tarih(line)
                if tarih:
                    return tarih

        # 3) Yalın tarih satırı (sağ üst / onay bloğu / "Yer, tarih")
        for i, line in enumerate(lines):
            if i in ilgi_blok:
                continue
            match = _YALIN_TARIH_SATIRI.match(line.strip())
            if match:
                return match.group(1)

        # 4) Düzenlenme kalıbı ("<tarih> günü ... tanzim edilmiştir")
        tanzim = tanzim_tarihi_bul(text)
        if tanzim:
            return tanzim

        # 5) Sözel (yazıyla) tarih ("<Ay> ayının <gün-yazı> günü") — rakamsal
        #    tarih içermeyen tutanak/olur belgelerinin kendi tarihi
        return sozel_tarih_bul(text)

    def _extract_document_number(self, text: str) -> str:
        """
        Belgenin KENDİ sayısını çıkarır (atıf sayılarından ayrıştırılmış).

        Resmî yazışma kuralı (Resmî Yazışmalarda Uygulanacak Usul ve
        Esaslar Hakkında Yönetmelik): belgenin sayısı, başlık bölümündeki
        "Sayı :" alan satırında yer alır. "İlgi" bloğunda anılan
        tarih/sayılar atıf yapılan ÖNCEKİ belgelere aittir ve bu belgenin
        sayısı DEĞİLDİR; bu yüzden yalnızca İlgi bloğu dışındaki "Sayı :"
        satırından çıkarım yapılır. (referans_numaralari alanı, metinde
        geçen TÜM referansları toplama davranışını korur; belgenin kendi
        sayısı ile atıf sayısı ayrımı bu alanla yapılır.)
        """
        lines = text.split("\n")
        ilgi_blok = self._ilgi_blok_satirlari(lines)
        for i, line in enumerate(lines):
            if i in ilgi_blok:
                continue
            if not _SAYI_SATIRI.match(turkish_lower(line)):
                continue
            deger = line.split(":", 1)[1] if ":" in line else ""
            match = re.match(r"\s*([A-Za-z0-9ÇĞİÖŞÜçğıöşü][\w.\-/]*)", deger)
            if not match:
                continue
            sayi = match.group(1).rstrip(".,;")
            # Klasik "Sayı-Tarih" düzeninde satırda yalnızca tarih kalmış
            # olabilir; tarih görünümlü değer belge sayısı sayılmaz.
            if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}", sayi):
                continue
            if len(sayi) >= 2:
                return sayi
        return ""

    def _extract_reference_numbers(self, text: str) -> list:
        """Sayı/referans numaralarını çıkarır (EBYS formatları dahil)."""
        refs = []
        adaylar = []
        for pattern in _REFERANS_DESENLERI:
            adaylar.extend(pattern.finditer(text))
        # Yalın "No :" adayları: adres/iletişim/kimlik bağlamındakiler elenir
        for match in _YALIN_NO.finditer(text):
            satir_basi = text.rfind("\n", 0, match.start()) + 1
            oncesi = turkish_lower(text[satir_basi:match.start()])
            if _NO_ADRES_BAGLAMI.search(oncesi):
                continue
            adaylar.append(match)

        for match in adaylar:
            value = match.group(1) if match.groups() else match.group(0)
            value = value.strip().rstrip(".,;")
            # Tek başına tarih görünümlü değerleri alma
            if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}", value):
                continue
            # T.C. Kimlik Numaralarını referans olarak alma
            if _tc_kimlik_gecerli(value):
                continue
            if len(value) >= 2:
                refs.append(value)
        return _benzersiz(refs)[:10]

    def _extract_tc_ids(self, text: str) -> list:
        """Checksum doğrulamasından geçen T.C. Kimlik Numaralarını çıkarır."""
        return _benzersiz([n for n in _TC_ADAY.findall(text) if _tc_kimlik_gecerli(n)])

    def _extract_phones(self, text: str) -> list:
        """Telefon numaralarını çıkarır (+90/0 önekli Türkiye formatları)."""
        phones = []
        for match in _TELEFON.finditer(text):
            value = match.group(0).strip()
            digits = re.sub(r"\D", "", value)
            if 10 <= len(digits) <= 12:
                phones.append(value)
        return _benzersiz(phones)

    def _extract_ibans(self, text: str) -> list:
        """IBAN numaralarını çıkarır (TR + 24 hane) ve boşluksuz normalize eder."""
        return _benzersiz([re.sub(r"\s", "", m) for m in _IBAN.findall(text)])

    def _extract_amounts(self, text: str) -> list:
        """Para tutarlarını (₺/TL) çıkarır."""
        amounts = []
        for pattern in _PARA_DESENLERI:
            amounts.extend(m.group(0).strip() for m in pattern.finditer(text))
        return _benzersiz(amounts)

    # ------------------------------------------------------------------
    # Konu / muhatap / ilgi
    # ------------------------------------------------------------------

    def _extract_subject(self, text: str) -> str:
        """Çok satırlı 'Konu :' değerini çıkarır."""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            match = re.match(r"\s*Konu\s*:\s*(.+)", line)
            if not match:
                continue
            parts = [match.group(1).strip()]
            # Devam satırları: girintili, boş olmayan ve yeni alan olmayan satırlar
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j]
                if not nxt.strip():
                    break
                if not nxt[:1].isspace():
                    break
                if _ALAN_SATIRI.match(nxt):
                    break
                parts.append(nxt.strip())
            return " ".join(parts).strip()
        return ""

    def _extract_recipient(self, text: str) -> str:
        """Muhatap bilgisini çıkarır (makam hitapları, 'Sayın X').

        Resmî yazışma kuralı: muhatap, tam satır BÜYÜK harflerle yazılan
        ve yönelme hâli ekiyle biten bir makam hitabıdır. Makam adları
        ünlü uyumlu "-lIğInA/-lUğUnA" ekini alır (MÜDÜRLÜĞÜNE,
        BAŞKANLIĞINA, VALİLİĞİNE, MÜŞAVİRLİĞİNE, KOORDİNATÖRLÜĞÜNE …);
        bu biçimler tek tek sayılmak yerine morfolojik desenle yakalanır.
        Hitabı izleyen parantezli birim açıklaması ("… VALİLİĞİNE
        (İl Müdürlüğü)") hitabın parçasıdır. Tüzel kişi muhataplar
        (… LTD. ŞTİ. / A.Ş.) da tam satır büyük harf yazılır.
        """
        # 1) Büyük harfli hitap satırı (tam satır, yönelme hâli ekli)
        hitap = re.compile(
            r"^(?:SAYIN\s+)?[A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\s.,\-&']{2,80}?"
            # Ünlü uyumlu -lIğInA/-lUğUnA (tekil) ve -lIklArInA/-lIklErInE (çoğul)
            r"(?:L[IİUÜ][GĞ][IİUÜ]N[AE]|L[AE]R[Iİ]N[AE]|"
            # Diğer makam/birim yönelme biçimleri
            r"MAKAMINA|DAİRESİNE|KOMİSYONUNA|KURULUNA|KURUMUNA|"
            r"BİRİMLERE|İLGİLİLERE|"
            # Tüzel kişi muhataplar
            r"LTD\.?\s*ŞTİ\.?|A\.Ş\.?)"
            # İsteğe bağlı parantezli birim açıklaması
            r"(?:\s*\([^)\n]{1,60}\))?$"
        )
        for line in text.split("\n"):
            stripped = line.strip().rstrip(",;")
            if stripped and hitap.match(stripped):
                return stripped

        # 2) "Sayın X" hitabı
        match = re.search(r"Say[ıi]n\s+([^\n,]{3,60})", text)
        if match:
            return match.group(1).strip()

        # 3) Satır içi "... makamına"
        match = re.search(r"([^\n]{3,60}?)\s+(?:MAKAMINA|makamına)", text)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_ilgi_references(self, text: str) -> list:
        """'İlgi :' / 'İlgi a)' referans satırlarını çıkarır."""
        refs = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            match = _ILGI_SATIRI.match(line)
            if not match:
                continue
            ilk = match.group(1).strip()
            if ilk:
                madde = _ILGI_MADDE.match(ilk)
                if madde:
                    refs.append(f"{madde.group(1)}) {madde.group(2).strip()}")
                else:
                    refs.append(ilk)
            # Devam eden "b) …" madde satırları
            for j in range(i + 1, min(i + 8, len(lines))):
                madde = _ILGI_MADDE.match(lines[j].strip())
                if not madde:
                    break
                refs.append(f"{madde.group(1)}) {madde.group(2).strip()}")
            break
        return _benzersiz(refs)

    # ------------------------------------------------------------------
    # Kurum ve kişi adları
    # ------------------------------------------------------------------

    @staticmethod
    def _dagitim_satirlari(lines: list) -> tuple:
        """
        Dağıtım bloğuna ait satır indekslerini ve birim adlarını döndürür.

        Kapsam: "Dağıtım :" başlık satırı ve onu izleyen (boş satıra kadar)
        liste satırları ile belgenin herhangi bir yerindeki "Gereği :" /
        "Bilgi :" alan satırları.

        Returns:
            (satir_indeksleri: set, birimler: list) ikilisi
        """
        indeksler = set()
        birimler = []

        def deger_ekle(line: str) -> None:
            value = line.split(":", 1)[1] if ":" in line else line
            value = value.strip().lstrip("-–—•*").strip()
            for parca in value.split(","):
                parca = parca.strip(" .;")
                if parca:
                    birimler.append(parca)

        i = 0
        while i < len(lines):
            tl = turkish_lower(lines[i])
            baslik = _DAGITIM_BASLIGI.match(tl)
            if baslik:
                indeksler.add(i)
                if (baslik.group(1) or "").strip():
                    deger_ekle(lines[i])
                # Başlığı izleyen blok: boş satıra kadar liste/alan satırları
                j = i + 1
                while j < len(lines) and lines[j].strip():
                    indeksler.add(j)
                    deger_ekle(lines[j])
                    j += 1
                i = j
            elif _DAGITIM_ALANI.match(tl):
                indeksler.add(i)
                deger_ekle(lines[i])
                i += 1
            else:
                i += 1
        return indeksler, birimler

    def _extract_distribution_units(self, text: str) -> list:
        """'Dağıtım :' / 'Gereği :' / 'Bilgi :' satırlarındaki birimleri çıkarır."""
        _, birimler = self._dagitim_satirlari(text.split("\n"))
        return _benzersiz(birimler)[:10]

    def _extract_organizations(self, text: str) -> list:
        """Kurum/birim adlarını çıkarır (antet satırları + satır içi desenler)."""
        orgs = []
        lines = text.split("\n")
        # Dağıtım bloğu satırları yazının GÖNDERİLDİĞİ birimleri taşır;
        # kurum adı (antet) kaynağı olarak kullanılmaz.
        dagitim_indeksleri, _ = self._dagitim_satirlari(lines)

        # 1) Antet satırları: kurum ekiyle biten kısa satırlar (BÜYÜK harf dahil)
        for i, line in enumerate(lines):
            if i in dagitim_indeksleri:
                continue
            stripped = line.strip().rstrip(",;.")
            if not stripped or len(stripped.split()) > 7:
                continue
            tl = turkish_lower(stripped)
            if any(tl.endswith(ek) for ek in _KURUM_EKLERI):
                temiz = re.sub(r"^(?:T\.\s?C\.?|Say[ıi]n|SAYIN)\s*", "", stripped).strip()
                if temiz:
                    orgs.append(temiz)

        # 2) Satır içi kurum adları ("Sayın" hitap öneki ayıklanır)
        for i, line in enumerate(lines):
            if i in dagitim_indeksleri:
                continue
            for match in _KURUM_INLINE.finditer(line):
                value = re.sub(r"^Say[ıi]n\s+", "", match.group(1).strip())
                orgs.append(value)

        # Büyük/küçük harf farklarını tek kayda indir (ilk görülen korunur)
        gorulen = set()
        benzersiz_orgs = []
        for org in orgs:
            key = turkish_lower(org)
            if key not in gorulen:
                gorulen.add(key)
                benzersiz_orgs.append(org)
        return benzersiz_orgs[:10]

    def _extract_person_names(self, text: str) -> list:
        """
        Kişi adlarını imza bloğu heuristikleriyle çıkarır.

        Kaynaklar: 'Ad Soyad :' alanı, 'Sayın X Y' hitapları, numaralı
        katılımcı listeleri ve belge sonundaki unvan üstü isim satırları.
        """
        names = []
        lines = text.split("\n")

        # 1) "Ad Soyad :" alanı
        for match in _AD_SOYAD_ALANI.finditer(text):
            names.append(match.group(1).strip())

        # 2) "Sayın Ad Soyad" hitapları
        for match in _SAYIN_KISI.finditer(text):
            names.append(match.group(1).strip())

        # 3) Numaralı listeler: "1. Dr. Mehmet Kaya - Unvan"
        for line in lines:
            match = _LISTE_KISI.match(line)
            if match:
                names.append(match.group(1).strip())

        # 4) İmza bloğu: son satırlardaki isim desenleri
        son_satirlar = lines[-15:]
        for idx, line in enumerate(son_satirlar):
            match = _IMZA_SATIRI.match(line)
            if not match:
                continue
            aday = match.group(1).strip()
            imza_cizgisi = bool(match.group(2))
            sonraki = son_satirlar[idx + 1].strip() if idx + 1 < len(son_satirlar) else ""
            sonraki_unvan = any(u in turkish_lower(sonraki) for u in _UNVAN_IPUCLARI)
            if imza_cizgisi or sonraki_unvan:
                names.append(aday)

        # Kurum/mekân/ay adı içeren adayları ele
        filtreli = []
        for name in names:
            tokens = {turkish_lower(t) for t in name.replace(".", " ").split()}
            if tokens & _KURUM_TOKENLERI:
                continue
            filtreli.append(name)

        return _benzersiz(filtreli)[:10]

    # ------------------------------------------------------------------
    # LLM zenginleştirmesi (opsiyonel)
    # ------------------------------------------------------------------

    def _enrich_with_llm(self, text: str, extracted: dict) -> None:
        """
        LLM erişilebilirse çıkarımı zenginleştirir.

        Regex sonuçları esastır: listeler yalnızca yeni benzersiz öğelerle
        genişletilir, skaler alanlar yalnızca boşsa doldurulur.
        Her hata sessizce yutulur (offline modda sistem tam çalışır).
        """
        try:
            from src.models.llm_wrapper import GUVENLIK_SISTEM_EKI, belge_blogu, get_default_llm

            llm = get_default_llm()
            if not llm.is_available():
                return

            schema_hint = (
                '{"kisi_adlari": ["<ad soyad>"], "kurum_adlari": ["<kurum>"], '
                '"konu": "<konu>", "muhatap": "<muhatap>"}'
            )
            # GÜVENLİK: evrak metni belge_blogu ile "yalnızca veri" olarak
            # işaretlenir (dolaylı prompt injection savunması, OWASP LLM01)
            prompt = f"""Aşağıdaki kamu evrakı metninden kişi adlarını, kurum adlarını,
konu ve muhatap bilgilerini çıkar. Yalnızca metinde açıkça geçen bilgileri yaz.

{belge_blogu(text, 3000)}"""
            data = llm.generate_json(
                prompt,
                schema_hint=schema_hint,
                system_prompt=(
                    "Sen kamu evraklarından yapılandırılmış bilgi çıkaran bir asistansın."
                    + GUVENLIK_SISTEM_EKI
                ),
            )

            for alan in ("kisi_adlari", "kurum_adlari"):
                yeni = data.get(alan)
                if isinstance(yeni, list):
                    mevcut = extracted.get(alan, [])
                    for item in yeni:
                        if isinstance(item, str) and item.strip() and item.strip() not in mevcut:
                            mevcut.append(item.strip())
                    extracted[alan] = mevcut[:10]

            for alan in ("konu", "muhatap"):
                if not extracted.get(alan):
                    deger = data.get(alan)
                    if isinstance(deger, str) and deger.strip():
                        extracted[alan] = deger.strip()

            logger.info("Çıkarım LLM ile zenginleştirildi.")
        except Exception as exc:
            logger.debug(f"LLM zenginleştirmesi atlandı: {exc}")
