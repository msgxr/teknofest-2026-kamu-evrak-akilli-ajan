# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Karar-kaynak eşlemesi (attribution) — 'neden bu karar' kanıt span'leri.

Bir kararı destekleyen kaynak metin parçalarını (span) bulur: çıkarılan varlıklar
(tarih, kurum, kişi, yer, T.C. kimlik, konu) ve ivedilik damgaları. Açıklanabilirlik
(explainability) katmanının çekirdeğidir; arayüzde evrak üzerinde renk-kodlu vurgu,
HTML işlem raporu ve API için kullanılabilir.

HALÜSİNASYON RİSKİ YOK: yalnızca kaynak metinde BİREBİR bulunan (grounded)
değerlerin konumları işaretlenir; span, kaynağın gerçek karakter aralığıdır.
ADDITIVE: kararı değiştirmez, yalnızca kararın kanıtını görünür kılar. Saf Python.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# İvedilik/gizlilik damgaları (Resmî Yazışma Yönetmeliği m.26/m.25 aileleri)
_DAMGALAR = ["GÜNLÜDÜR", "ACELE", "İVEDİ", "İVEDİDİR", "GİZLİ", "HİZMETE ÖZEL", "KİŞİYE ÖZEL"]


def _spanlar(metin: str, deger: str) -> List[List[int]]:
    """metin içinde deger'in tüm [başlangıç, bitiş] konumları (birebir eşleşme)."""
    if not deger or not metin:
        return []
    return [[m.start(), m.end()] for m in re.finditer(re.escape(str(deger)), metin)]


def vurgu_spanlari(metin: str, sonuc: Dict[str, Any], azami: int = 60) -> List[Dict[str, Any]]:
    """Kararı destekleyen kaynak span'lerini kategorize eder (grounded).

    Args:
        metin: Kaynak evrak metni.
        sonuc: Pipeline sonucu (bilgi_cikarim, onceliklendirme vb. içerir).
        azami: En fazla kaç vurgu döndürüleceği.

    Returns:
        [{kategori, deger, span:[b,e]}] — kaynakta gerçekten bulunan kanıtlar.
    """
    if not metin:
        return []
    bilgi = sonuc.get("bilgi_cikarim") or {}
    konu = bilgi.get("konu")
    kategoriler: Dict[str, List[str]] = {
        "tarih": list(bilgi.get("tarihler") or []),
        "kurum": list(bilgi.get("kurum_adlari") or []),
        "kisi": list(bilgi.get("kisi_adlari") or []),
        "yer": list(bilgi.get("yerler") or []),
        "tckn": list(bilgi.get("tc_kimlik") or []),
        "konu": [konu] if konu else [],
    }

    vurgular: List[Dict[str, Any]] = []
    gorulen = set()  # (kategori, başlangıç) tekrarını önle

    def ekle(kategori: str, deger: str) -> bool:
        for span in _spanlar(metin, deger):
            anahtar = (kategori, span[0])
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            vurgular.append({"kategori": kategori, "deger": str(deger), "span": span})
            if len(vurgular) >= azami:
                return True
        return False

    for kategori, degerler in kategoriler.items():
        for deger in degerler:
            if ekle(kategori, deger):
                return vurgular

    # İvedilik/gizlilik damgaları (triyaj/format kararlarının tetikleyicisi)
    for damga in _DAMGALAR:
        if damga in metin and ekle("damga", damga):
            return vurgular

    return vurgular
