"""Metamorfik / perturbasyon dayanıklılık testi araçları (CheckList-INV).

Etiket-KORUYAN metin bozulmaları üretir: bir evrağa anlamı değiştirmeyen
gürültü (diyakritik kaybı, yazım hatası, OCR-benzeri ikame, boşluk/noktalama
gürültüsü) eklenir ve sistemin kararının (tür / birim / öncelik / eksik-küme)
bu bozulmalar altında DEĞİŞMEMESİ (invaryans) beklenir. Gerçek kamu evrakı
taranmış/elle girilmiş olduğundan bu gürültü sahada yaygındır; sistemin ona
karşı gürbüzlüğü ölçülebilir bir güven kanıtıdır.

Literatür: Ribeiro, Wu, Guestrin, Singh (2020) "Beyond Accuracy: Behavioral
Testing of NLP Models with CheckList" (invariance/INV testleri); metamorfik
test kuramı (Chen vd.); TextAttack/TextFlint gürbüzlük değerlendirme desenleri.

Bozulmalar DETERMİNİSTİK (tohumlu) ve KÜRATÖRLÜ tutulur: aynı tohum aynı
varyantı üretir (tekrarlanabilirlik) ve dönüşümler evrak türünü/etiketini
değiştirmez. Saf Python; harici bağımlılık yok (offline-first çekirdek).
"""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Sequence, Tuple

# Türkçe diyakritik → ASCII karşılığı (kamu yazışmalarında diyakritiksiz
# yazım yaygındır; anlam korunur).
_DIYAKRITIK_TABLO = str.maketrans(
    {
        "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
    }
)


def diyakritik_katla(metin: str, rng: random.Random) -> str:
    """Tüm Türkçe diyakritikleri düzleştirir (ç→c, ş→s, ğ→g...).

    Deterministik; tohum kullanılmaz (imza tutarlılığı için alınır).
    """
    return metin.translate(_DIYAKRITIK_TABLO)


def bosluk_gurultu(metin: str, rng: random.Random, oran: float = 0.12) -> str:
    """Rastgele bazı boşlukları ikiye katlar (kopyala-yapıştır/OCR artığı)."""
    sonuc = []
    for ch in metin:
        sonuc.append(ch)
        if ch == " " and rng.random() < oran:
            sonuc.append(" ")
    return "".join(sonuc)


def yazim_gurultu(metin: str, rng: random.Random, azami_kelime: int = 3) -> str:
    """Birkaç uzun kelimede iç harf transpozisyonu (yaygın yazım hatası).

    Yalnızca 6+ harfli kelimelerin ORTA harfleri yer değiştirir; ilk/son harf
    ve kısa kelimeler korunur (okunabilirlik + etiket korunur).
    """
    kelimeler = metin.split(" ")
    uygun = [
        i for i, k in enumerate(kelimeler)
        if len(k) >= 6 and k.isalpha()
    ]
    if not uygun:
        return metin
    rng.shuffle(uygun)
    for i in uygun[:azami_kelime]:
        k = kelimeler[i]
        j = rng.randint(1, len(k) - 3)  # orta bölgede bir konum
        k_list = list(k)
        k_list[j], k_list[j + 1] = k_list[j + 1], k_list[j]
        kelimeler[i] = "".join(k_list)
    return " ".join(kelimeler)


# OCR'ın sık karıştırdığı karakter çiftleri (görsel benzerlik).
_OCR_CIFTLERI = [("İ", "I"), ("l", "ı"), ("rn", "m"), ("O", "0")]


def ocr_ikame(metin: str, rng: random.Random, azami: int = 4) -> str:
    """OCR-benzeri görsel karakter ikameleri (düşük sayıda, rastgele konum)."""
    sonuc = metin
    uygulanan = 0
    ciftler = list(_OCR_CIFTLERI)
    rng.shuffle(ciftler)
    for kaynak, hedef in ciftler:
        if uygulanan >= azami:
            break
        idx = sonuc.find(kaynak)
        if idx != -1:
            sonuc = sonuc[:idx] + hedef + sonuc[idx + len(kaynak):]
            uygulanan += 1
    return sonuc


def noktalama_gurultu(metin: str, rng: random.Random, oran: float = 0.15) -> str:
    """Bazı virgül/noktaları rastgele düşürür (gürültülü noktalama)."""
    sonuc = []
    for ch in metin:
        if ch in ",;" and rng.random() < oran:
            continue  # noktalamayı düşür
        sonuc.append(ch)
    return "".join(sonuc)


# Kayıtlı etiket-koruyan bozulmalar (isim → fonksiyon)
PERTURBASYONLAR: Dict[str, Callable[[str, random.Random], str]] = {
    "diyakritik": diyakritik_katla,
    "bosluk": bosluk_gurultu,
    "yazim": yazim_gurultu,
    "ocr": ocr_ikame,
    "noktalama": noktalama_gurultu,
}


def varyant_uret(
    metin: str, tohum: int, perturbasyon_adlari: Sequence[str] = ()
) -> List[Tuple[str, str]]:
    """Bir metinden deterministik, etiket-koruyan varyantlar üretir.

    Args:
        metin: Kaynak evrak metni
        tohum: Deterministik tohum (aynı tohum → aynı varyantlar)
        perturbasyon_adlari: Uygulanacak bozulmalar (boş → tümü)

    Returns:
        [(bozulma_adi, varyant_metin)] listesi
    """
    adlar = list(perturbasyon_adlari) or list(PERTURBASYONLAR)
    varyantlar: List[Tuple[str, str]] = []
    for k, ad in enumerate(adlar):
        fn = PERTURBASYONLAR.get(ad)
        if fn is None:
            continue
        rng = random.Random(tohum + k)
        varyantlar.append((ad, fn(metin, rng)))
    return varyantlar


def invaryans_orani(orijinal_karar: object, varyant_kararlari: Sequence[object]) -> float:
    """Kararın varyantlar altında değişmeme (invaryans) oranı [0-1].

    1.0 = tam gürbüz (hiçbir bozulma kararı değiştirmedi).
    """
    if not varyant_kararlari:
        return 1.0
    ayni = sum(1 for k in varyant_kararlari if k == orijinal_karar)
    return ayni / len(varyant_kararlari)
