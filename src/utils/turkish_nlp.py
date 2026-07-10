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
