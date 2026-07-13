# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""İstatistiksel anlamlılık: güven aralıkları + eşleştirilmiş test.

Küçük değerlendirme setlerinde (n=16) çıplak nokta tahminleri (ör. "0,750 (12/16)")
bilimsel olarak zayıftır. Bu modül %95 güven aralığı (Wilson skor + bootstrap) ve
iki sistemi karşılaştıran eşleştirilmiş McNemar testini ekler. Küçük n'de GENİŞ
aralıklar bir kusur değil, DÜRÜSTLÜK göstergesidir (aşırı-iddiadan kaçınır).

Literatür: Wilson (1927) skor aralığı; Efron (1979) bootstrap; McNemar (1947)
eşleştirilmiş test. Saf Python (stdlib math + random); offline-first korunur.
Deterministik: bootstrap sabit tohumla çalışır (tekrarlanabilirlik).
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Sequence


def wilson_araligi(basari: int, toplam: int, z: float = 1.96) -> List[float]:
    """İkili oran için Wilson skor güven aralığı (varsayılan z=1.96 → %95).

    Normal yaklaşımın aksine küçük n ve uç oranlarda (0/1'e yakın) isabetlidir.
    """
    if toplam <= 0:
        return [0.0, 0.0]
    p = basari / toplam
    n = toplam
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yaricap = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / payda
    return [round(max(0.0, merkez - yaricap), 4), round(min(1.0, merkez + yaricap), 4)]


def bootstrap_araligi(
    dogru_maskesi: Sequence[bool],
    tekrar: int = 2000,
    alfa: float = 0.05,
    tohum: int = 1234,
) -> List[float]:
    """Doğru/yanlış maskesinden (bool dizisi) oran için bootstrap %(1-alfa) GA.

    Deterministik (tohumlu) — aynı girdi aynı aralığı verir.
    """
    n = len(dogru_maskesi)
    if n == 0:
        return [0.0, 0.0]
    rng = random.Random(tohum)
    oranlar = []
    for _ in range(tekrar):
        toplam = sum(1 for _ in range(n) if dogru_maskesi[rng.randrange(n)])
        oranlar.append(toplam / n)
    oranlar.sort()
    alt = oranlar[int((alfa / 2) * tekrar)]
    ust = oranlar[min(tekrar - 1, int((1 - alfa / 2) * tekrar))]
    return [round(alt, 4), round(ust, 4)]


def mcnemar(a_dogru: Sequence[bool], b_dogru: Sequence[bool]) -> Dict[str, Any]:
    """İki sistemin (A, B) aynı örneklerdeki doğru/yanlış maskelerini eşleştirilmiş
    McNemar testiyle karşılaştırır (süreklilik düzeltmeli χ², 1 serbestlik derecesi).

    b = A doğru & B yanlış, c = A yanlış & B doğru. p-değeri 1-df χ² kuyruğu
    (math.erfc ile kesin). anlamli_0_05: p < 0.05.
    """
    b = sum(1 for x, y in zip(a_dogru, b_dogru) if x and not y)
    c = sum(1 for x, y in zip(a_dogru, b_dogru) if not x and y)
    if b + c == 0:
        return {"b": b, "c": c, "istatistik": 0.0, "p_deger": 1.0, "anlamli_0_05": False}
    chi = (abs(b - c) - 1) ** 2 / (b + c)  # Yates süreklilik düzeltmesi
    p = math.erfc(math.sqrt(chi / 2))  # 1-df χ² üst kuyruğu (kesin)
    return {
        "b": b, "c": c,
        "istatistik": round(chi, 4),
        "p_deger": round(p, 4),
        "anlamli_0_05": p < 0.05,
    }


def oran_ozeti(dogru_maskesi: Sequence[bool]) -> Dict[str, Any]:
    """Bir doğru/yanlış maskesi için nokta tahmini + Wilson + bootstrap %95 GA."""
    n = len(dogru_maskesi)
    basari = sum(1 for d in dogru_maskesi if d)
    return {
        "nokta": round(basari / n, 4) if n else None,
        "basari": basari,
        "toplam": n,
        "wilson_95": wilson_araligi(basari, n),
        "bootstrap_95": bootstrap_araligi(dogru_maskesi),
    }
