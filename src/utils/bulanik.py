# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Bulanık dizgi eşleme — Damerau-Levenshtein düzenleme mesafesi + benzerlik.

Kamu evrak asistanının niyet motorunun "bulanık" katmanını besler: kullanıcıların
yazım hatalarına (harf düşmesi/eklenmesi, bitişik harf yer değiştirmesi) ve
morfolojik varyasyona dayanıklı token eşleşmesi sağlar. Böylece "snıflandır",
"yönledir", "mevzat" gibi hatalı girdiler doğru niyete bağlanabilir.

Damerau-Levenshtein mesafesi: bir dizgiyi diğerine dönüştürmek için gereken
minimum EKLEME, SİLME, DEĞİŞTİRME ve BİTİŞİK harf TRANSPOZİSYONU sayısı. Klasik
Levenshtein'den farkı, "ba"→"ab" gibi komşu harf yer değiştirmesini tek işlem
sayması — Türkçe klavye/yazım hatalarında sık görülür.

Saf Python, offline; hiçbir harici bağımlılık yok (offline-first korunur).
Literatür: Damerau (1964), Levenshtein (1966).
"""

from __future__ import annotations


def damerau_levenshtein(a: str, b: str, tavan: int | None = None) -> int:
    """a → b için minimum düzenleme (ekle/sil/değiştir/transpoze) sayısı.

    Args:
        a, b: Karşılaştırılacak dizgiler.
        tavan: Verilirse ve mesafe bu tavanı aşacaksa erken çıkılıp ``tavan + 1``
            döndürülür (bantlı optimizasyon — büyük farklarda gereksiz hesap yok).

    Returns:
        Düzenleme mesafesi (>= 0).
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    if tavan is not None and abs(la - lb) > tavan:
        return tavan + 1

    onceki2: list[int] | None = None          # i-2 satırı (transpozisyon için)
    onceki = list(range(lb + 1))              # i-1 satırı
    for i in range(1, la + 1):
        simdiki = [i] + [0] * lb
        satir_min = simdiki[0]
        for j in range(1, lb + 1):
            maliyet = 0 if a[i - 1] == b[j - 1] else 1
            deger = min(
                onceki[j] + 1,               # silme
                simdiki[j - 1] + 1,          # ekleme
                onceki[j - 1] + maliyet,     # değiştirme (eşitse 0)
            )
            if (i > 1 and j > 1 and onceki2 is not None
                    and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]):
                deger = min(deger, onceki2[j - 2] + 1)  # transpozisyon
            simdiki[j] = deger
            if deger < satir_min:
                satir_min = deger
        if tavan is not None and satir_min > tavan:
            return tavan + 1
        onceki2 = onceki
        onceki = simdiki
    return onceki[lb]


def benzerlik(a: str, b: str) -> float:
    """0..1 normalize benzerlik: ``1 − mesafe / max(len)``. 1.0 = birebir eşit."""
    if a == b:
        return 1.0
    ust = max(len(a), len(b))
    if ust == 0:
        return 1.0
    return 1.0 - damerau_levenshtein(a, b, tavan=ust) / ust


def en_yakin(sorgu: str, adaylar, esik: float = 0.0):
    """Adaylar içinde ``sorgu``ya en benzer (kelime, skor) çiftini döndürür.

    Args:
        sorgu: Aranan token.
        adaylar: Karşılaştırılacak kelime dizisi.
        esik: Bu benzerliğin altındaki eşleşmeler yok sayılır.

    Returns:
        (en_iyi_kelime, benzerlik) — eşik altında kalırsa (None, 0.0).
    """
    en_iyi, en_iyi_skor = None, 0.0
    for aday in adaylar:
        s = benzerlik(sorgu, aday)
        if s > en_iyi_skor:
            en_iyi, en_iyi_skor = aday, s
    if en_iyi_skor < esik:
        return None, 0.0
    return en_iyi, round(en_iyi_skor, 4)
