# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Emsal-tabanlı akıl yürütme (Case-Based Reasoning) — ADVISORY karar katmanı.

Düşük güvenli bir kararda, geçmiş ONAYLI kayıtlardan (kayıt defteri) getirilen
benzer emsallerin doğrulanmış tür/birim dağılımını bir "öneri/önsel" olarak
sunar ve mevcut kararla çeliştiğinde uyarır. Sistem kullandıkça denetim izinden
ÖĞRENEREK isabet artırma potansiyeli kazanır (yeniden eğitim gerekmez).

ADVISORY'dir: kararı EZMEZ; yalnızca öneri + çelişki uyarısı üretir (insan
onayına yardımcı). Boş defterde (emsal yoksa) etkisizdir → offline/değerlendirme
davranışı korunur.

Literatür: Case-Based Reasoning (Aamodt & Plaza 1994); bellek-akışı ajanı
(Park vd. 2023, Generative Agents). Saf Python.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Optional, Sequence


def emsal_onerisi(
    emsaller: Sequence[Dict[str, Any]],
    mevcut_tur: Optional[str] = None,
    mevcut_birim: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Emsallerden çoğunluk tür/birim önselini + mevcut kararla çelişki uyarısını
    üretir. Emsal yoksa None döner (boş defter → etkisiz).

    Returns:
        {emsal_sayisi, cogunluk_tur, cogunluk_birim, celiskiler[], aciklama} | None
    """
    gecerli = [e for e in emsaller if e.get("tur") or e.get("birim")]
    if not gecerli:
        return None
    turler = Counter(e["tur"] for e in gecerli if e.get("tur"))
    birimler = Counter(e["birim"] for e in gecerli if e.get("birim"))
    cok_tur = turler.most_common(1)[0][0] if turler else None
    cok_birim = birimler.most_common(1)[0][0] if birimler else None

    celiskiler = []
    if cok_tur and mevcut_tur and cok_tur != mevcut_tur:
        celiskiler.append(
            f"Emsal çoğunluğu türü '{cok_tur}' iken sistem '{mevcut_tur}' önerdi."
        )
    if cok_birim and mevcut_birim and cok_birim != mevcut_birim:
        celiskiler.append(
            f"Emsal çoğunluğu birimi '{cok_birim}' iken sistem '{mevcut_birim}' önerdi."
        )

    return {
        "emsal_sayisi": len(gecerli),
        "cogunluk_tur": cok_tur,
        "cogunluk_birim": cok_birim,
        "celiskiler": celiskiler,
        "aciklama": (
            f"{len(gecerli)} benzer geçmiş evrak; çoğunlukla tür '{cok_tur}', "
            f"birim '{cok_birim}'."
        ),
    }
