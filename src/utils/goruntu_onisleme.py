# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Adaptif görüntü ön-işleme — OCR öncesi okunabilirlik iyileştirme (multimodal).

Taranmış/telefonla çekilmiş evrak görüntüsünü OCR'a vermeden önce düzeltir:
gri tonlama → eğiklik giderme (deskew) → ölçekleme → gürültü giderme → adaptif
ikileştirme. Şartname 'çoklu ortam (multimodal) anlama'yı açıktan puanlar;
ön-işleme, eğik/gölgeli gerçek taramada OCR isabetini belirgin yükseltir.

Ayrıca OCR güven telemetrisinden belge kalitesi (`ocr_kalite`) üretir → düşük
kalitede yeniden-OCR/insan onayına yönlendiren '4. kapı' sinyali.

Bağımlılık ZARİF DÜŞÜMLÜ: opencv (cv2) varsa tam hat; her adım try/except ile
sarılı, herhangi biri başarısızsa o ana kadarki en iyi görüntü döner; cv2 yoksa
görüntü OLDUĞU GİBİ döner. Çekirdek .txt yolu HİÇ etkilenmez.

Literatür: Otsu (1979) eşikleme; adaptif eşikleme; deskew (minAreaRect).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

_ASGARI_YUKSEKLIK = 1000  # bu yükseklikaltı görüntüler OCR için büyütülür
_AZAMI_YUKSEKLIK = 4000   # aşırı büyütmeyi (bellek) engelle


def on_isle(image: Any) -> Any:
    """PIL görüntüsünü OCR için hazırlar (gri + deskew + ölçek + eşik).

    cv2 yoksa veya bir adım başarısızsa görüntü olabildiğince korunur (asla
    hata yükseltmez — sunum/ön-işleme katmanı çekirdeği bozamaz).
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except Exception:
        return image  # görüntü kütüphaneleri yok → ham görüntü

    try:
        arr = np.array(image.convert("L"))  # gri tonlama
    except Exception:
        return image

    arr = _guvenli(lambda a: _deskew(a, cv2, np), arr)
    arr = _guvenli(lambda a: _olcekle(a, cv2), arr)
    arr = _guvenli(lambda a: cv2.medianBlur(a, 3), arr)  # gürültü giderme
    arr = _guvenli(
        lambda a: cv2.adaptiveThreshold(
            a, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        ),
        arr,
    )
    try:
        return Image.fromarray(arr)
    except Exception:
        return image


def _guvenli(fn, arr):
    """Bir adımı uygular; başarısızsa girdiyi olduğu gibi döndürür."""
    try:
        sonuc = fn(arr)
        return sonuc if sonuc is not None else arr
    except Exception:
        return arr


def _deskew(arr, cv2, np):
    """Metin eğikliğini tahmin edip düzeltir (minAreaRect); ihmal edilebilir
    açıda dokunmaz."""
    _, ikili = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    koordinatlar = np.column_stack(np.where(ikili > 0))
    if len(koordinatlar) < 20:
        return arr
    aci = cv2.minAreaRect(koordinatlar)[-1]
    # DÜZELTME: minAreaRect açısı OpenCV sürümüne göre eski [-90,0) VEYA yeni
    # (0,90] (>=4.5.1) döner. Eski tek-dallı ifade, yeni sürümde neredeyse dik
    # bir sayfayı (~90°) -90° döndürüp OCR'ı bozuyordu. Her iki konvansiyonu da
    # küçük düzeltme açısına (-45,45] indir (sürümden bağımsız).
    if aci < -45:
        aci = -(90 + aci)      # eski OpenCV konvansiyonu
    elif aci > 45:
        aci = -(aci - 90)      # yeni OpenCV konvansiyonu (>=4.5.1)
    else:
        aci = -aci
    if abs(aci) < 0.5:
        return arr
    h, w = arr.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), aci, 1.0)
    return cv2.warpAffine(
        arr, M, (w, h), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _olcekle(arr, cv2):
    """Küçük görüntüleri OCR için büyütür (DPI etkisi); üst sınırı aşmaz."""
    h, w = arr.shape
    if h >= _ASGARI_YUKSEKLIK:
        return arr
    olcek = min(_ASGARI_YUKSEKLIK / h, _AZAMI_YUKSEKLIK / h)
    return cv2.resize(
        arr, (int(w * olcek), int(h * olcek)), interpolation=cv2.INTER_CUBIC
    )


def ocr_kalite(kelime_guvenleri: Sequence[float]) -> Dict[str, Any]:
    """OCR kelime güvenlerinden (0-100; -1 = boş) belge kalitesi + kapı sinyali.

    Returns:
        {ortalama_guven, dusuk_guven_orani, kalite, insan_onayi_onerilir}
        kalite: yuksek | orta | dusuk. Düşük → yeniden-OCR/insan onayı önerilir.
    """
    gecerli = [float(c) for c in kelime_guvenleri if c is not None and c >= 0]
    if not gecerli:
        return {
            "ortalama_guven": 0.0, "dusuk_guven_orani": 1.0,
            "kalite": "dusuk", "insan_onayi_onerilir": True,
        }
    ortalama = sum(gecerli) / len(gecerli)
    dusuk_oran = sum(1 for c in gecerli if c < 60) / len(gecerli)
    if ortalama >= 80 and dusuk_oran < 0.2:
        kalite = "yuksek"
    elif ortalama >= 60:
        kalite = "orta"
    else:
        kalite = "dusuk"
    return {
        "ortalama_guven": round(ortalama, 1),
        "dusuk_guven_orani": round(dusuk_oran, 3),
        "kalite": kalite,
        "insan_onayi_onerilir": kalite == "dusuk",
    }
