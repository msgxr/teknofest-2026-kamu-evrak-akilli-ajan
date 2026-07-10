"""
Eksik Bilgi Tespit Agent — Evrakta bulunması gereken eksik bilgileri tespit etme.

Evrak türüne göre zorunlu alanlar kontrol edilir; kontroller
`extracted_info`'nun doğrulanmış alanlarına dayanır (ör. tc_kimlik
checksum'lı, tarih/telefon/eposta regex doğrulamalı). Her eksik için
alan, açıklama, öncelik (kritik/önemli/bilgi) ve giderme önerisi üretilir.

Şartname Referansı (Görev 1):
    "Evrakta bulunması gereken ancak eksik olan bilgileri tespit edebilme"
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.agents.info_extraction_agent import tanzim_tarihi_bul
from src.utils.turkish_nlp import turkish_lower, turkish_upper

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.missing_info")

# Türkçe aksan katlama tablosu: ASCII alan adları ile Türkçe karakterli
# metnin ortak bir biçimde karşılaştırılabilmesi için (ç→c, ğ→g, ı→i, …)
_AKSAN_TABLOSU = str.maketrans("çğıöşü", "cgiosu")


def _ascii_katla(s: str) -> str:
    """Küçük harfli metindeki Türkçe aksanlı karakterleri ASCII'ye katlar."""
    return s.translate(_AKSAN_TABLOSU)

# Evrak türüne göre zorunlu alanlar
ZORUNLU_ALANLAR = {
    # Dilekçenin zorunlu unsurları 3071 sayılı Dilekçe Hakkı Kanunu'na
    # dayanır: ad-soyad, imza ve iş/ikametgâh ADRESİ. Ayrıca bir talep
    # metni ve tarih beklenir. "Konu :" başlığı dilekçede zorunlu bir
    # alan değildir (talep metninin kendisi konuyu taşır); telefon/
    # e-posta gibi ek iletişim kanalları da yasal zorunluluk değildir
    # (iletişim ihtiyacını adres karşılar).
    "dilekce": [
        "tarih", "ad_soyad", "tc_kimlik", "adres", "talep_metni", "imza",
    ],
    "ust_yazi": [
        "tarih", "sayi", "konu", "muhatap", "ilgi", "metin", "imza", "kurum_bilgisi",
    ],
    "cevap_yazisi": [
        "tarih", "sayi", "konu", "muhatap", "ilgi", "cevap_metni", "imza",
    ],
    "bilgilendirme": [
        "tarih", "sayi", "konu", "metin", "dagitim", "imza",
    ],
    "tutanak": [
        "tarih", "saat", "yer", "katilimcilar", "gundem", "kararlar", "imzalar",
    ],
    # Not: "özet" bölümü raporun evrensel zorunlu unsuru değildir (serbest
    # akışlı raporlarda bulunmayabilir); bulgular/sonuç içerik sinyaliyle aranır.
    "rapor": [
        "tarih", "baslik", "hazirlayan", "bulgular", "sonuc", "imza",
    ],
    "genelge": [
        "tarih", "sayi", "konu", "metin", "dagitim",
    ],
    "onayli_belge": [
        "tarih", "sayi", "onaylayan", "onay_metni",
    ],
    "diger": [
        "tarih", "konu", "metin",
    ],
}

# Alan açıklamaları
_ALAN_ACIKLAMALARI = {
    "tarih": "Evrak tarihi belirtilmemiş",
    "saat": "Saat bilgisi belirtilmemiş",
    "sayi": "Evrak sayı/referans numarası eksik",
    "konu": "Konu alanı belirtilmemiş",
    "muhatap": "Muhatap/alıcı bilgisi eksik",
    "imza": "İmza bilgisi bulunamadı",
    "imzalar": "Katılımcı imzaları bulunamadı",
    "ad_soyad": "Başvuru sahibinin adı soyadı eksik",
    "tc_kimlik": "Geçerli bir T.C. Kimlik Numarası bulunamadı",
    "adres": "Adres bilgisi eksik",
    "iletisim": "Telefon veya e-posta gibi iletişim bilgisi eksik",
    "ilgi": "İlgi (referans) bilgisi eksik",
    "dagitim": "Dağıtım listesi belirtilmemiş",
    "kurum_bilgisi": "Kurum bilgisi/antet eksik",
    "yer": "Yer bilgisi belirtilmemiş",
    "katilimcilar": "Katılımcı listesi eksik",
    "gundem": "Gündem maddeleri belirtilmemiş",
    "kararlar": "Alınan kararlar belirtilmemiş",
    "metin": "Evrak gövde metni eksik veya çok kısa",
    "talep_metni": "Talep metni eksik veya çok kısa",
    "cevap_metni": "Cevap metni eksik veya çok kısa",
    "baslik": "Rapor başlığı eksik",
    "hazirlayan": "Raporu hazırlayan bilgisi eksik",
    "ozet": "Özet bölümü eksik",
    "bulgular": "Bulgular bölümü eksik",
    "sonuc": "Sonuç/değerlendirme bölümü eksik",
    "onaylayan": "Onay makamı bilgisi eksik",
    "onay_metni": "Onay ifadesi bulunamadı",
}

# Eksikliğin nasıl giderileceğine dair tek cümlelik öneriler
_ALAN_ONERILERI = {
    "tarih": "Evrakın düzenlendiği tarihi gün.ay.yıl biçiminde (ör. 11.07.2026) ekleyin.",
    "saat": "İşlemin/toplantının başlangıç ve bitiş saatini (ör. 14:00 - 16:30) ekleyin.",
    "sayi": "Kurum EBYS'sinden alınan sayı/referans numarasını 'Sayı :' alanına yazın.",
    "konu": "Evrak içeriğini özetleyen kısa bir 'Konu :' satırı ekleyin.",
    "muhatap": "Evrakın gönderileceği makamı açıkça yazın (ör. '… MÜDÜRLÜĞÜNE').",
    "imza": "Belgeyi düzenleyenin ad-soyad, unvan ve ıslak/elektronik imzasını ekleyin.",
    "imzalar": "Tüm katılımcıların ad-soyad ve imzalarını tutanak sonuna ekleyin.",
    "ad_soyad": "Başvuru sahibinin adını ve soyadını belge sonuna ekleyin.",
    "tc_kimlik": "Başvuru sahibinin 11 haneli geçerli T.C. Kimlik Numarasını ekleyin.",
    "adres": "Başvuru sahibinin yerleşim yeri adresini ekleyin (3071 sayılı Kanun gereği zorunludur).",
    "iletisim": "Telefon numarası veya e-posta adresi gibi bir iletişim kanalı belirtin.",
    "ilgi": "Atıf yapılan önceki yazıların tarih ve sayısını 'İlgi :' satırında listeleyin.",
    "dagitim": "Yazının gönderileceği birimleri 'Dağıtım:' bölümünde Gereği/Bilgi ayrımıyla listeleyin.",
    "kurum_bilgisi": "Belge başlığına kurum adını içeren resmi antet (T.C. …) ekleyin.",
    "yer": "Toplantının/işlemin yapıldığı yeri açıkça yazın.",
    "katilimcilar": "Katılımcıların ad-soyad ve unvanlarını liste halinde ekleyin.",
    "gundem": "Görüşülen gündem maddelerini numaralandırarak yazın.",
    "kararlar": "Alınan kararları madde madde ve açık ifadelerle yazın.",
    "metin": "Evrakın amacını ve dayanağını açıklayan gövde metnini genişletin.",
    "talep_metni": "Talebinizi açık ve net biçimde ifade eden bir paragraf ekleyin.",
    "cevap_metni": "İlgi yazıdaki hususlara karşılık gelen cevap paragraflarını ekleyin.",
    "baslik": "Belgenin üstüne içeriği yansıtan bir başlık ekleyin.",
    "hazirlayan": "Raporu hazırlayanın ad-soyad ve unvanını belirtin.",
    "ozet": "Raporun başına bulguları özetleyen kısa bir özet bölümü ekleyin.",
    "bulgular": "İnceleme sırasında elde edilen bulguları ayrı bir bölümde sunun.",
    "sonuc": "Raporun sonuna değerlendirme ve sonuç bölümü ekleyin.",
    "onaylayan": "Onay makamının ad-soyad ve unvanını belirtin.",
    "onay_metni": "Onay ifadesini (ör. 'Uygun görülmüştür' / 'OLUR') ve onay tarihini ekleyin.",
}

# Öncelik seviyeleri
_KRITIK_ALANLAR = {
    "tarih", "sayi", "konu", "imza", "ad_soyad", "imzalar",
    "talep_metni", "cevap_metni", "onay_metni", "onaylayan",
}
_ONEMLI_ALANLAR = {
    "muhatap", "ilgi", "tc_kimlik", "kurum_bilgisi", "adres", "metin",
    "katilimcilar", "kararlar", "gundem", "yer", "saat", "dagitim",
    "baslik", "hazirlayan", "bulgular", "sonuc",
}

# Evrak türüne özel öncelik geçersiz kılmaları
_ONCELIK_GECERSIZ_KILMA = {
    "dilekce": {"adres": "kritik", "tc_kimlik": "kritik"},
    "tutanak": {"katilimcilar": "kritik", "kararlar": "kritik"},
}


class MissingInfoAgent:
    """
    Eksik bilgi tespit agent'ı.

    Evrak türüne göre bulunması gereken zorunlu alanları, doğrulanmış
    çıkarım sonuçlarını (extracted_info) esas alarak kontrol eder ve
    eksik olanları öncelik + giderme önerisiyle raporlar.
    """

    def __init__(self) -> None:
        logger.info("Eksik Bilgi Tespit Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evraktaki eksik bilgileri tespit eder ve state.missing_info'ya yazar."""
        evrak_turu = state.classification.get("tur", "diger")
        text = state.raw_text
        extracted_info = state.extracted_info or {}

        zorunlu = ZORUNLU_ALANLAR.get(evrak_turu, ZORUNLU_ALANLAR["diger"])
        eksikler = []

        for alan in zorunlu:
            if not self._check_field_exists(alan, text, extracted_info, evrak_turu):
                eksikler.append({
                    "alan": alan,
                    "aciklama": self._get_field_description(alan),
                    "oncelik": self._get_field_priority(alan, evrak_turu),
                    "oneri": self._get_field_suggestion(alan),
                })

        # Kritik > önemli > bilgi sırasıyla raporla
        siralama = {"kritik": 0, "önemli": 1, "bilgi": 2}
        eksikler.sort(key=lambda e: siralama.get(e["oncelik"], 3))
        state.missing_info = eksikler

        if eksikler:
            logger.warning(f"Eksik bilgi tespit edildi: {len(eksikler)} alan")
            for e in eksikler:
                logger.debug(f"  - [{e['oncelik']}] {e['alan']}: {e['aciklama']}")
        else:
            logger.info("Tüm zorunlu alanlar mevcut.")

        return state

    # ------------------------------------------------------------------
    # Alan kontrolleri
    # ------------------------------------------------------------------

    def _check_field_exists(
        self, field: str, text: str, extracted: dict, evrak_turu: str = ""
    ) -> bool:
        """Bir alanın evrakta mevcut olup olmadığını kontrol eder."""
        tl = turkish_lower(text)

        field_checks = {
            # Evrak tarihi: belgenin KENDİ tarihi aranır (İlgi satırındaki
            # ve "… tarihli" kalıbındaki atıf tarihleri sayılmaz; ayrım
            # info_extraction'da "evrak_tarihi" olarak yapılır). Tutanak
            # türünde gövdedeki düzenlenme kalıbı ("<tarih> günü ... tanzim
            # edilmiştir") da evrak tarihi kaynağıdır — özet bu tarihi
            # gösterirken eksik listesinin "tarih yok" demesi önlenir.
            # Anahtar yoksa (eski çağrılar) genel tarih listesine düşülür.
            "tarih": lambda: bool(extracted.get("evrak_tarihi"))
            or (evrak_turu == "tutanak" and bool(tanzim_tarihi_bul(text)))
            or ("evrak_tarihi" not in extracted and bool(extracted.get("tarihler"))),
            "saat": lambda: bool(re.search(r"\b\d{1,2}[:.][0-5]\d\b", text)),
            "sayi": lambda: bool(extracted.get("referans_numaralari"))
            or bool(re.search(r"(?m)^\s*say[ıi]\s*:", tl)),
            "konu": lambda: bool(extracted.get("konu")),
            "muhatap": lambda: bool(extracted.get("muhatap")),
            "imza": lambda: self._has_signature(text, tl),
            "imzalar": lambda: "imzalar" in tl
            or "imzalanmıştır" in tl
            or len(re.findall(r"_{4,}", text)) >= 2
            or self._has_signature(text, tl),
            "ad_soyad": lambda: bool(extracted.get("kisi_adlari")),
            # Checksum doğrulamasından geçen TC kimlik (geçersizler alınmaz)
            "tc_kimlik": lambda: bool(extracted.get("tc_kimlik")),
            # Adres, "Adres :" etiketli alanla ya da adres-biçimli bir
            # satırla (mahalle/cadde/sokak kısaltması + kapı no/ilçe ayracı)
            # verilir; gövde metninde geçen "mahalle sakinleri" gibi anlatım
            # ifadeleri gönderici adresi sayılmaz.
            "adres": lambda: self._has_address(text, tl),
            "iletisim": lambda: bool(extracted.get("telefon")) or bool(extracted.get("eposta")),
            "ilgi": lambda: bool(extracted.get("ilgi_referanslari"))
            or bool(re.search(r"(?m)^\s*ilgi\s*:", tl)),
            "metin": lambda: len(text.strip()) > 100,
            "talep_metni": lambda: len(text.strip()) > 50,
            "cevap_metni": lambda: len(text.strip()) > 50,
            "dagitim": lambda: "dağıtım" in tl or bool(re.search(r"(?m)^\s*gereği\s*:", tl)),
            "kurum_bilgisi": lambda: bool(extracted.get("kurum_adlari")),
            # Yer: tutanak/toplantı belgelerinde yer bilgisi "Yer :" /
            # "Toplantı Yeri :" alan satırıyla ya da mekân sözcükleriyle verilir.
            "yer": lambda: bool(
                re.search(r"(?m)^\s*(?:toplantı\s+)?yer[i]?\s*:", tl)
            )
            or any(k in tl for k in ["yeri", "salon", "adres", "mahal"]),
            "katilimcilar": lambda: "katılımcı" in tl or "hazır bulunan" in tl
            or "iştirak eden" in tl,
            # Gündem: görüşülen husus "Gündem" listesiyle verilebileceği gibi
            # tutanaklarda "Konu :" satırı veya "görüşülen konular" bölümü de
            # aynı işlevi görür (tek konulu tutanaklarda gündem listesi olmaz).
            "gundem": lambda: "gündem" in tl
            or bool(extracted.get("konu"))
            or "görüşülen konu" in tl
            or "toplantı konusu" in tl,
            "kararlar": lambda: "karar" in tl,
            "baslik": lambda: self._has_title(text),
            "hazirlayan": lambda: any(
                k in tl for k in ["hazırlayan", "düzenleyen", "raportör", "rapor eden"]
            ),
            "ozet": lambda: "özet" in tl,
            # Bulgular/sonuç: raporlar bölüm başlığı yerine serbest akışta
            # da yazılabilir; tespit/değerlendirme fiilleri içerik sinyalidir.
            # Türkçe eklemeli dil: fiil kökleriyle arama yapılır ki
            # "görülmüştür/görülmektedir/izlenmiş/incelemek" gibi tüm
            # çekimler yakalansın.
            "bulgular": lambda: any(
                k in tl
                for k in [
                    "bulgu", "tespit", "görülm", "belirlen", "saptan",
                    "gözlem", "incele", "izlen", "kaydedil", "ölçül",
                ]
            ),
            "sonuc": lambda: any(
                k in tl
                for k in [
                    "sonuç", "kanaat", "netice", "öneri", "önerilmektedir",
                    "değerlendirilmiştir", "teklif edilmektedir", "uygun olacağı",
                ]
            ),
            "onaylayan": lambda: "onaylayan" in tl or "olur" in tl
            or self._has_signature(text, tl),
            "onay_metni": lambda: any(
                k in tl for k in ["uygun görülmüştür", "onaylanmıştır", "tasdik", "olur"]
            ),
        }

        checker = field_checks.get(field)
        if checker:
            return checker()

        # Genel kontrol: alan adı metinde geçiyor mu. Alan adları ASCII
        # (ör. "gundem"), metin ise Türkçe karakterli (ör. "gündem")
        # olduğundan iki taraf da aksan katlanarak karşılaştırılır.
        return _ascii_katla(field.replace("_", " ")) in _ascii_katla(tl)

    @staticmethod
    def _has_address(text: str, tl: str) -> bool:
        """
        Gönderici/muhatap adresinin varlığını kontrol eder.

        Adres iki biçimde bulunur: (1) "Adres :" etiketli alan;
        (2) adres-biçimli satır — mahalle/cadde/sokak kısaltmasıyla
        birlikte kapı numarası veya ilçe/il ayracı içeren satır
        ("Liman Mah. Küpeşte Sk. No: 5 Yelkenova / DENİZOVA").
        Gövde anlatımında geçen "mahalle sakinleri" gibi ifadeler
        adres sayılmaz.
        """
        if re.search(r"(?m)^\s*adres\w*\s*:", tl):
            return True
        for satir in tl.split("\n"):
            konum_var = any(
                k in satir
                for k in ["mah.", "mahallesi", "cad.", "caddesi", "sk.",
                          "sokağı", "sokak no", "bulvarı", "blv.", "apt."]
            )
            if not konum_var:
                continue
            biçim_var = bool(re.search(r"no\s*[:.]?\s*\d", satir)) or \
                bool(re.search(r"\d{1,4}\s*/\s*\d{1,4}", satir)) or \
                " / " in satir or bool(re.search(r"\b\d{5}\b", satir))
            if biçim_var:
                return True
        return False

    @staticmethod
    def _has_signature(text: str, tl: str) -> bool:
        """İmza varlığını kontrol eder (anahtar kelime, çizgi bloğu, unvan satırı)."""
        if "imza" in tl or re.search(r"_{4,}", text):
            return True
        # Belge sonunda unvan satırı (imza bloğu göstergesi)
        son_kisim = turkish_lower("\n".join(text.strip().split("\n")[-6:]))
        unvanlar = (
            "müdür", "başkan", "uzman", "müsteşar", "şef", "memur",
            "vali", "kaymakam", "müşavir", "sekreter",
        )
        return any(
            re.search(r"(?m)^\s*.{0,50}" + u + r"[ıiu]?\s*$", son_kisim) for u in unvanlar
        )

    @staticmethod
    def _has_title(text: str) -> bool:
        """İlk satırlarda büyük harfli bir başlık olup olmadığını kontrol eder."""
        for line in [l.strip() for l in text.split("\n") if l.strip()][:6]:
            if len(line) >= 5 and line == turkish_upper(line) and any(c.isalpha() for c in line):
                return True
        return False

    # ------------------------------------------------------------------
    # Açıklama / öncelik / öneri
    # ------------------------------------------------------------------

    def _get_field_description(self, field: str) -> str:
        """Bir alan için açıklama döndürür."""
        return _ALAN_ACIKLAMALARI.get(field, f"'{field}' alanı eksik")

    def _get_field_priority(self, field: str, evrak_turu: str = "") -> str:
        """Bir alan için öncelik seviyesi döndürür (türe özel geçersiz kılmalı)."""
        override = _ONCELIK_GECERSIZ_KILMA.get(evrak_turu, {})
        if field in override:
            return override[field]
        if field in _KRITIK_ALANLAR:
            return "kritik"
        if field in _ONEMLI_ALANLAR:
            return "önemli"
        return "bilgi"

    def _get_field_suggestion(self, field: str) -> str:
        """Eksikliğin nasıl giderileceğine dair tek cümlelik öneri döndürür."""
        return _ALAN_ONERILERI.get(field, f"'{field.replace('_', ' ')}' bilgisini belgeye ekleyin.")
