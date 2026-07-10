"""
Türkçe NLP yardımcı araçları.

Türkçe'ye özel metin işleme fonksiyonları.
"""

import re
import unicodedata
from typing import Optional


# Türkçe durak kelimeleri (stop words)
TURKCE_DURAK_KELIMELERI = {
    "bir", "ve", "bu", "da", "de", "ile", "için", "olan", "olarak", "gibi",
    "veya", "ancak", "fakat", "ama", "çünkü", "hem", "ne", "ya", "ki",
    "daha", "en", "çok", "az", "her", "tüm", "hiç", "bazı", "diğer",
    "aynı", "böyle", "şu", "o", "ben", "sen", "biz", "siz", "onlar",
    "ise", "olup", "olduğu", "olan", "olarak", "üzere", "kadar", "sonra",
    "önce", "arasında", "içinde", "üzerinde", "altında", "yanında",
    "tarafından", "hakkında", "ilgili", "göre", "karşı", "rağmen",
}


def normalize_turkish(text: str) -> str:
    """
    Türkçe metni normalize eder.

    - Büyük/küçük harf dönüşümü (Türkçe'ye uygun)
    - Fazla boşlukları temizler
    - Unicode normalizasyonu
    """
    # Unicode normalizasyonu
    text = unicodedata.normalize("NFC", text)

    # Türkçe'ye uygun küçük harf
    text = turkish_lower(text)

    # Fazla boşlukları temizle
    text = re.sub(r"\s+", " ", text).strip()

    return text


def turkish_lower(text: str) -> str:
    """Türkçe'ye uygun küçük harf dönüşümü (I -> ı, İ -> i)."""
    tr_map = str.maketrans("İIÇÖÜŞĞ", "iıçöüşğ")
    return text.translate(tr_map).lower()


def turkish_upper(text: str) -> str:
    """Türkçe'ye uygun büyük harf dönüşümü (i -> İ, ı -> I)."""
    tr_map = str.maketrans("iıçöüşğ", "İIÇÖÜŞĞ")
    return text.translate(tr_map).upper()


def remove_stopwords(text: str) -> str:
    """Türkçe durak kelimelerini metinden çıkarır."""
    words = text.split()
    filtered = [w for w in words if turkish_lower(w) not in TURKCE_DURAK_KELIMELERI]
    return " ".join(filtered)


def extract_sentences(text: str) -> list[str]:
    """Metinden cümleleri çıkarır."""
    # Türkçe cümle sonu işaretleri
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def count_words(text: str) -> int:
    """Metindeki kelime sayısını döndürür."""
    return len(text.split())


def clean_text(text: str) -> str:
    """
    Metni temizler.

    - Ekstra boşlukları ve satır sonlarını düzenler
    - Kontrol karakterlerini temizler
    """
    # Kontrol karakterlerini temizle (satır sonu hariç)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Birden fazla boş satırı teke indir
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Satır başı ve sonu boşlukları temizle
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


# ----------------------------------------------------------------------
# Hafif dil sezimi (Türkçe / Türkçe değil) — harici bağımlılık yok
# ----------------------------------------------------------------------

# Türkçe alfabeye özgü harfler (dil sezimi sinyali 1)
TURKCE_OZGU_HARFLER = set("çğıöşüÇĞİÖŞÜ")

# Başka dillerde de sık geçtiği için dil seziminde AYIRT EDİCİ sayılmayan
# durak kelimeler (ör. "de"/"en" İspanyolca-Fransızcada, "her"/"ben"
# İngilizcede yaygındır). Sezimde bunların dışındaki durak kelimeler
# kullanılır; böylece yabancı metinler yanlışlıkla Türkçe sayılmaz.
_DIL_SEZIMINDE_BELIRSIZ_DURAKLAR = {
    "de", "da", "en", "o", "ne", "ya", "her", "ben", "sen", "az",
}

# Ayırt edici durak kelime kümesi (modül yüklenirken bir kez hesaplanır)
_DIL_AYIRT_EDICI_DURAKLAR = TURKCE_DURAK_KELIMELERI - _DIL_SEZIMINDE_BELIRSIZ_DURAKLAR

# Dil sezimi eşikleri:
# - Türkçe metinlerde ç/ğ/ı/ö/ş/ü harfleri tipik olarak harflerin %5-12'sidir;
#   %1 eşiği aksan oranı düşük Türkçe metinleri de yakalar. Yabancı metinde
#   tek tük özel ad ("İstanbul" gibi) bu eşiği aşamaz.
# - Aksansız (ASCII) yazılmış Türkçe metinlerde özgü harf sinyali kaybolur;
#   bu durumda "bir", "ve", "bu" gibi ayırt edici durak kelimelerin kelime
#   oranı (Türkçe düzyazıda tipik olarak %8-15) devreye girer.
_TURKCE_KARAKTER_ORAN_ESIGI = 0.01
_DURAK_KELIME_ORAN_ESIGI = 0.05
_DIL_SEZIMI_MIN_HARF = 20


def turkish_language_signals(text: str) -> dict:
    """
    Hafif Türkçe dil sezimi sinyallerini hesaplar.

    İki bağımsız sinyal üretilir:
    - turkce_karakter_orani: Türkçe'ye özgü harflerin (ç, ğ, ı, ö, ş, ü)
      metindeki tüm harflere oranı.
    - durak_kelime_orani: ayırt edici Türkçe durak kelimelerinin tüm
      kelimelere oranı (aksansız yazılmış Türkçe metinleri de yakalar).

    Returns:
        {"harf_sayisi": int, "kelime_sayisi": int,
         "turkce_karakter_orani": float, "durak_kelime_orani": float}
    """
    harf_sayisi = 0
    ozgu_harf = 0
    for ch in text:
        if ch.isalpha():
            harf_sayisi += 1
            if ch in TURKCE_OZGU_HARFLER:
                ozgu_harf += 1

    kelimeler = re.findall(r"[^\W\d_]+", turkish_lower(text))
    durak_sayisi = sum(1 for k in kelimeler if k in _DIL_AYIRT_EDICI_DURAKLAR)

    return {
        "harf_sayisi": harf_sayisi,
        "kelime_sayisi": len(kelimeler),
        "turkce_karakter_orani": (
            round(ozgu_harf / harf_sayisi, 4) if harf_sayisi else 0.0
        ),
        "durak_kelime_orani": (
            round(durak_sayisi / len(kelimeler), 4) if kelimeler else 0.0
        ),
    }


def is_turkish_text(text: str) -> bool:
    """
    Metnin Türkçe olup olmadığını hafif kurallarla sezer.

    Sinyallerden HERHANGİ BİRİ eşiği aşarsa metin Türkçe kabul edilir:
    - Türkçe'ye özgü harf oranı (ç/ğ/ı/ö/ş/ü) eşiği aşıyorsa, veya
    - ayırt edici Türkçe durak kelime örtüşmesi eşiği aşıyorsa
      (aksansız/ASCII yazılmış Türkçe metinleri yakalar).

    Karar verilemeyecek kadar kısa metinlerde (harf sayısı eşiğin altında)
    engelleyici olmamak için Türkçe varsayılır.
    """
    sinyaller = turkish_language_signals(text)
    if sinyaller["harf_sayisi"] < _DIL_SEZIMI_MIN_HARF:
        return True
    return (
        sinyaller["turkce_karakter_orani"] >= _TURKCE_KARAKTER_ORAN_ESIGI
        or sinyaller["durak_kelime_orani"] >= _DURAK_KELIME_ORAN_ESIGI
    )
