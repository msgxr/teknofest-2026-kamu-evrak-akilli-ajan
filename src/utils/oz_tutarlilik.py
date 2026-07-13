# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Öz-tutarlılık (self-consistency) oylaması — kalibre LLM güveni.

LLM en yüksek belirsizlikte (düşük-güven eskalasyonu) çağrılır; tek örnekleme
en kırılgan yöntemdir. K orta-sıcaklık örneklemenin kapalı-liste çoğunluk oyu,
uzlaşı oranını KALİBRE bir güven skoruna çevirir (mevcut conformal/selektif
katmana beslenebilir): tüm örneklemeler hemfikirse yüksek güven, dağınıksa düşük.

Boş/tek örnekte mevcut davranış korunur; yalnızca opsiyonel LLM katmanı devrede
ve K>1 iken tetiklenir (offline çekirdek etkilenmez).

Literatür: Wang vd. (2022) "Self-Consistency Improves Chain of Thought Reasoning
in Language Models" (arXiv:2203.11171). Saf Python.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence, Tuple


def cogunluk_oyu(kararlar: Sequence[Optional[str]]) -> Tuple[Optional[str], float]:
    """Çoğunluk kararı + uzlaşı oranı [0-1].

    Args:
        kararlar: K örneklemenin tekil kararları (ör. tür anahtarları).

    Returns:
        (karar, uzlasi) — geçerli karar yoksa (None, 0.0). uzlasi = çoğunluk
        kararının örneklemeler içindeki oranı (kalibre güven vekili).
    """
    gecerli = [k for k in kararlar if k]
    if not gecerli:
        return None, 0.0
    sayim = Counter(gecerli)
    karar, adet = sayim.most_common(1)[0]
    return karar, round(adet / len(gecerli), 4)
