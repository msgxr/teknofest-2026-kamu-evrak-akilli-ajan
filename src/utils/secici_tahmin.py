# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Seçici sınıflandırma (selective classification / reject option) + OOD skoru.

Sınıflandırıcının HER karara körü körüne güvenmek yerine, güveni düşük veya
belirsiz kararları "kapsam dışı / güven yetersiz" işaretleyip insan onayına
devretmesini sağlar (mevcut HITL kuyruğu). Chow (1970) reddetme kuralı: güven
bir eşiğin altındaysa karar reddedilir. Belirsizlik üç sinyalden türetilir:
  1. MSP eksikliği (1 − en yüksek softmax olasılığı),
  2. marj (en yüksek iki sınıf arası fark — düşükse iki tür arasında kararsız),
  3. OOV/kapsam-dışı oranı (sözlük-dışı öznitelik → dağılım kayması işareti).

Literatür: Chow (1970) optimum reddetme kuralı; Hendrycks & Gimpel (2017)
Maximum Softmax Probability OOD baseline; Geifman & El-Yaniv (2017) selective
classification (risk-coverage). Saf Python; offline-first çekirdek korunur.
"""

from __future__ import annotations

from typing import Dict, Sequence


def belirsizlik_skoru(
    tum_skorlar: Dict[str, float], oov_orani: float = 0.0
) -> Dict[str, float]:
    """MSP, marj ve OOV'den birleşik belirsizlik skoru üretir.

    Returns:
        {"msp", "marj", "belirsizlik"} — belirsizlik [0-1]: 0 çok güvenli,
        1 çok belirsiz.
    """
    if not tum_skorlar:
        return {"msp": 0.0, "marj": 0.0, "belirsizlik": 1.0}
    sirali = sorted(tum_skorlar.values(), reverse=True)
    msp = sirali[0]
    marj = sirali[0] - (sirali[1] if len(sirali) > 1 else 0.0)
    oov = min(max(oov_orani, 0.0), 1.0)
    belirsizlik = (1 - msp) * 0.5 + (1 - marj) * 0.3 + oov * 0.2
    return {
        "msp": round(msp, 4),
        "marj": round(marj, 4),
        "belirsizlik": round(min(max(belirsizlik, 0.0), 1.0), 4),
    }


def chow_reddet(guven: float, esik: float = 0.6) -> bool:
    """Chow reddetme kuralı: güven eşiğin altındaysa reddet (insana devret)."""
    return guven < esik


def kapsam_risk(
    guvenler: Sequence[float], dogrular: Sequence[bool], esik: float = 0.6
) -> Dict[str, float]:
    """Verilen reddetme eşiğinde seçici tahmin dengesi.

    Eşiği geçen (kabul edilen) kararlarda kapsama (kabul oranı), risk (kabul
    edilenlerdeki hata oranı) ve reddedilen (insana devredilen) sayısı. İdeal:
    yüksek kapsama + düşük risk — reddetmenin gerçekten hataları elediğini
    gösterir.
    """
    n = len(guvenler)
    if n == 0:
        return {"esik": esik, "kapsama": 0.0, "risk": 0.0, "reddedilen": 0}
    kabul = [(g, d) for g, d in zip(guvenler, dogrular) if g >= esik]
    hata = sum(1 for _, d in kabul if not d)
    return {
        "esik": esik,
        "kapsama": round(len(kabul) / n, 4),
        "risk": round(hata / len(kabul), 4) if kabul else 0.0,
        "reddedilen": n - len(kabul),
    }
