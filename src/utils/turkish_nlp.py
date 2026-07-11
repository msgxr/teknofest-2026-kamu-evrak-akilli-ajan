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
    """
    Metinden cümleleri çıkarır.

    Nokta her zaman cümle sonu değildir (TDK Yazım Kılavuzu, "Nokta"):
    - Sayıdan sonra gelen nokta sıra bildirir ("5. etap" = beşinci etap)
      ve cümleyi bitirmez.
    - Kısaltmalardan sonraki nokta (vb., vs., Dr., Av., Sk., Mah., No.,
      md. ...) cümle sonu değildir.
    - Nokta ile yazılan büyük harfli kısaltmalar ve ad baş harfleri
      (T.C., A.Ş., "Ahmet Y.") cümleyi bitirmez.
    Bu konumlarda yanlış bölünen parçalar sonraki parçayla birleştirilir.
    """
    # Noktayla biten ama cümleyi bitirmeyen yaygın kısaltmalar: unvan,
    # adres ve gönderme kısaltmaları (resmî yazışmalarda sık geçer).
    kisaltmalar = {
        # Unvan/hitap kısaltmaları
        "dr", "av", "prof", "doç", "yrd", "uzm", "öğr", "arş", "sn",
        # Adres kısaltmaları
        "mah", "sk", "sok", "cad", "cd", "bulv", "blv", "apt", "no", "kat",
        # Gönderme/genelleme kısaltmaları
        "vb", "vs", "vd", "bkz", "örn", "md", "hk", "tel",
    }

    parcalar = re.split(r"(?<=[.!?])\s+", text)
    cumleler: list[str] = []
    for parca in parcalar:
        parca = parca.strip()
        if not parca:
            continue
        if cumleler and cumleler[-1].endswith("."):
            onceki = cumleler[-1]
            son = re.search(r"(\S+)\.$", onceki)
            birlestir = False
            if son:
                govde = son.group(1).strip("(\"'“”‘’")
                if govde.isdigit():
                    # Sıra sayısı: kısa sayılar ("5.", "12.") hemen her
                    # zaman ordinaldir; uzun sayılar (yıl vb.) yalnızca
                    # devamı büyük harfle başlamıyorsa (yeni cümle
                    # başlangıcı değilse) birleştirilir.
                    ilk = parca[0]
                    birlestir = len(govde) <= 2 or not (
                        ilk.isalpha() and turkish_upper(ilk) == ilk
                    )
                elif turkish_lower(govde) in kisaltmalar:
                    birlestir = True
                elif re.fullmatch(r"(?:[A-ZÇĞİÖŞÜ]\.)*[A-ZÇĞİÖŞÜ]", govde):
                    # T.C., A.Ş. gibi noktalı kısaltmalar ve ad baş harfleri
                    birlestir = True
            if birlestir:
                cumleler[-1] = onceki + " " + parca
                continue
        cumleler.append(parca)
    return [s for s in cumleler if len(s) > 10]


def count_words(text: str) -> int:
    """Metindeki kelime sayısını döndürür."""
    return len(text.split())


# ----------------------------------------------------------------------
# Morfolojik desen üretimi (son-ünsüz yumuşaması)
# ----------------------------------------------------------------------

# Türkçe küçük harf sınıfı (regex köşeli parantez içeriği). Sözcük-başı
# sınırı denetiminde kullanılır; düzeltme işaretli â/î/û harfleri de
# resmî yazışma Türkçesinde geçtiği için dahildir.
TR_KUCUK_HARF_SINIFI = "a-zçğıöşüâîû"

# Süreksiz sert ünsüzlerin (p, ç, t, k) yumuşamış karşılıkları.
# k → ğ tipik biçimdir (ekmek → ekmeği); "nk" ile biten ve bazı alıntı
# sözcüklerde ise g'ye döner (renk → rengi) — bu yüzden k için üç seçenek.
_YUMUSAMA_SINIFLARI = {
    "p": "[pb]",
    "ç": "[çc]",
    "t": "[td]",
    "k": "[kğg]",
}

# Yumuşama alternatifi uygulanacak asgari kök uzunluğu: çok kısa köklerde
# ("at" → "a[td]" deseni "ad" sözcüğünü de yakalar) alternatif biçim başka
# sözcüklerle çakışabilir; üç harf ve üzeri köklerde bu risk pratikte yoktur.
_YUMUSAMA_MIN_UZUNLUK = 3


def govde_desen(kelime: str, harf_sinifi: str = TR_KUCUK_HARF_SINIFI) -> str:
    """
    Türkçe son-ünsüz yumuşamasına dayanıklı, sözcük-başı sınırlı regex
    desen kaynağı üretir.

    Dilbilgisel gerekçe: Türkçede süreksiz sert ünsüzlerle (p, ç, t, k)
    biten sözcükler ünlüyle başlayan bir ek aldığında son ünsüz iki ünlü
    arasında kalır ve YUMUŞAR (ünsüz yumuşaması): kitap → kitabı,
    sonuç → sonucu, kanat → kanadı, lojistik → lojistiği, renk → rengi.
    Yalın biçimle yapılan önek araması bu çekimlenmiş biçimleri kaçırır;
    üretilen desen son ünsüzün hem sert hem yumuşamış biçimine izin verir:
        'lojistik' → '(?<![harf])lojisti[kğg]'
        'sonuç'    → '(?<![harf])sonu[çc]'
        'kitap'    → '(?<![harf])kita[pb]'
    Desen sözcük başında bir harf sınırı arar (önünde harf olamaz) ve
    kelimenin SONUNU açık bırakır; böylece ek almış biçimler ("lojistiğin",
    "sonucuna") eşleşirken alakasız köklerin içindeki rastlantısal
    parçalar eşleşmez. Kelime öbeklerinde ("eğitim ihtiyaç") ek kelime
    sonuna geldiği için yumuşama yalnızca son karaktere uygulanır.

    Not: Yumuşama bazı tek heceli ve alıntı sözcüklerde gerçekleşmez
    (süt → sütü, hukuk → hukuku); desen iki biçime de izin verdiğinden bu
    istisnalar eşleşmeyi bozmaz. ASCII'ye katlanmış (aksansız) metinlerde
    de çalışır: ç'nin katlanmış hali (c) yumuşamış biçimle, ğ'nin
    katlanmış hali (g) '[kğg]' sınıfıyla zaten örtüşür.

    Args:
        kelime: Küçük harfli anahtar kelime veya kelime öbeği
        harf_sinifi: Sözcük-başı sınırında "harf" sayılacak regex
            karakter sınıfı içeriği

    Returns:
        re.compile'a verilebilecek desen kaynağı (str)
    """
    kelime = kelime.strip()
    son = kelime[-1:]
    if son in _YUMUSAMA_SINIFLARI and len(kelime) >= _YUMUSAMA_MIN_UZUNLUK:
        govde = re.escape(kelime[:-1]) + _YUMUSAMA_SINIFLARI[son]
    else:
        govde = re.escape(kelime)
    return "(?<![%s])%s" % (harf_sinifi, govde)


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
