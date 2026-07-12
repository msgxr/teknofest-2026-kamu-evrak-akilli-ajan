"""Çapraz tutarlılık doğrulayıcı (multi-agent verification katmanı).

Hattın sonunda çalışır ve ajan çıktılarını BİRBİRİNE karşı kural tabanlı
çapraz doğrular; tek bir ajanın kendi içinde tutarlı ama ajanlar-arası çelişkili
kararlarını yakalar. Çelişki bulursa insan onayı ÖNERİR — kararı bloklamaz
(öneri niteliği korunur, kamu gerçekliğine uygun sorumlu otomasyon).

Denetimler (hepsi deterministik, saf Python):
  1. Özet sadakati: özetteki sayı/tarih olguları kaynak evrakta bulunmalı
     (özet ajanı kaynakta olmayan bilgi üretmiş mi?).
  2. Taslak mevzuat temelliliği: taslakta atıf yapılan "NNNN sayılı" mevzuat,
     mevzuat ajanının öneri listesinde bulunmalı (taslak ajanı halüsinasyon
     atıf yapmış mı?).

Literatür: verifier-agent / çok-ajanlı doğrulama; Du vd. (2023) Multiagent
Debate; RAGAS faithfulness fikri. Offline-first çekirdek korunur.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from src.utils.ozet_kalite import sadakat

_SAYILI = re.compile(r"\b(\d{3,5})\s*sayılı")


def _mevzuat_numaralari(mevzuat_eslesmeleri: Optional[Sequence[Dict[str, Any]]]) -> set:
    """Öneri listesindeki mevzuatların "NNNN sayılı" numaralarını çıkarır."""
    numaralar = set()
    for m in mevzuat_eslesmeleri or []:
        for alan in (
            m.get("mevzuat_adi", ""), m.get("baslik", ""),
            m.get("madde_no", ""), m.get("gerekce", ""),
        ):
            numaralar.update(_SAYILI.findall(str(alan)))
    return numaralar


def tutarlilik_denetle(
    ozet: str,
    kaynak_metin: str,
    taslak: str,
    mevzuat_eslesmeleri: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Ajan çıktılarını çapraz doğrular; çelişki listesi + öneri döndürür.

    Returns:
        {"tutarli": bool, "celiskiler": [{tur, aciklama}], "insan_onayi_onerilir": bool}
    """
    celiskiler: List[Dict[str, str]] = []

    # 1. Özet sadakati (özet ajanı ↔ kaynak metin)
    if ozet and kaynak_metin:
        oz_sadakat = sadakat(ozet, kaynak_metin)
        if oz_sadakat < 1.0:
            celiskiler.append({
                "tur": "ozet_sadakat",
                "aciklama": (
                    f"Özet, kaynak evrakta bulunmayan sayısal olgu içeriyor "
                    f"(sadakat {oz_sadakat})."
                ),
            })

    # 2. Taslak mevzuat temelliliği (taslak ajanı ↔ mevzuat ajanı)
    izinli = _mevzuat_numaralari(mevzuat_eslesmeleri)
    if taslak and izinli:  # yalnızca öneri listesi numara içeriyorsa denetle
        taslak_atiflari = set(_SAYILI.findall(taslak))
        ekstra = taslak_atiflari - izinli
        if ekstra:
            celiskiler.append({
                "tur": "taslak_atif",
                "aciklama": (
                    "Taslak, mevzuat öneri listesinde bulunmayan mevzuata atıf "
                    f"yapıyor: {sorted(ekstra)} sayılı."
                ),
            })

    return {
        "tutarli": not celiskiler,
        "celiskiler": celiskiler,
        "insan_onayi_onerilir": bool(celiskiler),
    }
