# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Güven kalibrasyonu ölçümü ve sıcaklık ölçekleme (temperature scaling).

Sınıflandırma güveni (softmax olasılığı) ile gerçek doğruluk arasındaki
uyumu nicel ölçer. Bir sistemin "güven 0,90" dediği kararlar gerçekten
%90 doğruysa güven KALİBREDİR; değilse (aşırı/eksik güven) karar eşikleri
(ör. 0,6 insan-onayı kapısı) keyfî kalır. Bu modül kalibrasyonu ölçülebilir
kılar ve tek skaler sıcaklıkla düzeltir.

Literatür:
  - Guo, Pleiss, Sun, Weinberger (2017) "On Calibration of Modern Neural
    Networks" — ECE ve temperature scaling.
  - Naeini, Cooper, Hauskrecht (2015) — reliability diagram / ECE kutulama.
  - Brier (1950) — olasılıksal tahmin skoru.
  - Geifman & El-Yaniv (2017) "Selective Classification" — risk-coverage, AURC.

Tümü saf Python; hiçbir harici bağımlılık yok (offline-first çekirdek korunur).
Sıcaklık YALNIZCA argmax'ı değiştirmez; kararı değil, yalnızca güveni kalibre
eder. Held-out setlerde yalnızca ÖLÇÜM yapılır; sıcaklık öğrenimi geliştirme
seti üzerinde yapılır (değerlendirme bütünlüğü korunur).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence


def softmax(skorlar: Dict[str, float], sicaklik: float = 1.0) -> Dict[str, float]:
    """Ham skorları sıcaklıkla ölçeklenmiş softmax olasılıklarına çevirir.

    sicaklik > 1 dağılımı yumuşatır (güveni düşürür), < 1 keskinleştirir.
    Sayısal kararlılık için en yüksek skor çıkarılır; argmax korunur.
    """
    if not skorlar:
        return {}
    if sicaklik <= 0:
        sicaklik = 1e-6
    en_yuksek = max(skorlar.values())
    usler = {k: math.exp((v - en_yuksek) / sicaklik) for k, v in skorlar.items()}
    toplam = sum(usler.values()) or 1.0
    return {k: v / toplam for k, v in usler.items()}


def ece_mce(
    guvenler: Sequence[float],
    dogrular: Sequence[bool],
    kutu_sayisi: int = 10,
) -> Dict[str, Any]:
    """Expected/Maximum Calibration Error + reliability diagram kutuları.

    guvenler: her tahmin için tahmin edilen sınıfın güveni [0,1].
    dogrular: her tahmin doğru mu (bool).
    ECE = Σ (|kutu|/N) · |doğruluk(kutu) − güven(kutu)|  (0 = mükemmel kalibre).
    """
    n = len(guvenler)
    if n == 0:
        return {"ece": 0.0, "mce": 0.0, "kutular": []}
    kutular: List[Dict[str, Any]] = []
    ece = 0.0
    mce = 0.0
    for i in range(kutu_sayisi):
        alt = i / kutu_sayisi
        ust = (i + 1) / kutu_sayisi
        if i == kutu_sayisi - 1:  # son kutuda üst sınır dahil
            idx = [j for j in range(n) if alt <= guvenler[j] <= ust]
        else:
            idx = [j for j in range(n) if alt <= guvenler[j] < ust]
        if not idx:
            kutular.append({
                "aralik": [round(alt, 2), round(ust, 2)],
                "sayi": 0, "ortalama_guven": None, "dogruluk": None,
            })
            continue
        ort_guven = sum(guvenler[j] for j in idx) / len(idx)
        dogruluk = sum(1 for j in idx if dogrular[j]) / len(idx)
        fark = abs(dogruluk - ort_guven)
        ece += (len(idx) / n) * fark
        mce = max(mce, fark)
        kutular.append({
            "aralik": [round(alt, 2), round(ust, 2)],
            "sayi": len(idx),
            "ortalama_guven": round(ort_guven, 4),
            "dogruluk": round(dogruluk, 4),
        })
    return {"ece": round(ece, 4), "mce": round(mce, 4), "kutular": kutular}


def brier_skoru(guvenler: Sequence[float], dogrular: Sequence[bool]) -> float:
    """İkili Brier skoru: tahmin edilen sınıfın güveni ile doğruluk (0/1)
    arasındaki ortalama kare hata. 0 en iyi, 1 en kötü."""
    n = len(guvenler)
    if n == 0:
        return 0.0
    return round(
        sum((guvenler[j] - (1.0 if dogrular[j] else 0.0)) ** 2 for j in range(n)) / n,
        4,
    )


def risk_kapsama(guvenler: Sequence[float], dogrular: Sequence[bool]) -> Dict[str, Any]:
    """Risk-coverage eğrisi + AURC (area under risk-coverage curve).

    Tahminler güvene göre azalan sırada; her kapsama düzeyinde (en güvenli
    ilk %k) hata oranı (risk) hesaplanır. Düşük AURC = güven, hataları iyi
    sıralıyor; yani selektif tahmin (düşük güvenli olanı insana devretme)
    işe yarar. Şartname 0,6 insan-onayı kapısının FAYDA kanıtıdır.
    """
    n = len(guvenler)
    if n == 0:
        return {"aurc": 0.0, "egri": []}
    sirali = sorted(range(n), key=lambda j: guvenler[j], reverse=True)
    egri: List[Dict[str, float]] = []
    kumulatif_hata = 0
    alan = 0.0
    for k, j in enumerate(sirali, 1):
        if not dogrular[j]:
            kumulatif_hata += 1
        risk = kumulatif_hata / k
        egri.append({"kapsama": round(k / n, 4), "risk": round(risk, 4)})
        alan += risk
    return {"aurc": round(alan / n, 4), "egri": egri}


def _nll(olasiliklar: Sequence[Dict[str, float]], dogru_siniflar: Sequence[str]) -> float:
    """Negatif log-olabilirlik (düşük = iyi kalibrasyon)."""
    n = len(olasiliklar)
    if n == 0:
        return 0.0
    toplam = 0.0
    for olasilik, dogru in zip(olasiliklar, dogru_siniflar):
        toplam += -math.log(max(olasilik.get(dogru, 0.0), 1e-12))
    return toplam / n


def sicaklik_ogren(
    olasilik_listesi: Sequence[Dict[str, float]],
    dogru_siniflar: Sequence[str],
    alt: float = 0.25,
    ust: float = 5.0,
    tur_sayisi: int = 40,
) -> float:
    """NLL'i minimize eden tek skaler sıcaklığı altın-oran aramasıyla öğrenir.

    Mevcut olasılık dağılımını (softmax çıktısı) sözde-logit'e çevirir
    (log p) ve softmax(log p / T) ile yeniden kalibre eder. argmax değişmez,
    yalnızca güven kalibre olur. Geliştirme seti üzerinde çağrılmalıdır.
    """
    if not olasilik_listesi:
        return 1.0
    sozde_logitler = [
        {k: math.log(max(v, 1e-12)) for k, v in olasilik.items()}
        for olasilik in olasilik_listesi
    ]

    def maliyet(sicaklik: float) -> float:
        olas = [softmax(z, sicaklik) for z in sozde_logitler]
        return _nll(olas, dogru_siniflar)

    altin = (math.sqrt(5) - 1) / 2  # ≈ 0,618
    a, b = alt, ust
    c = b - altin * (b - a)
    d = a + altin * (b - a)
    fc, fd = maliyet(c), maliyet(d)
    for _ in range(tur_sayisi):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - altin * (b - a)
            fc = maliyet(c)
        else:
            a, c, fc = c, d, fd
            d = a + altin * (b - a)
            fd = maliyet(d)
    return round((a + b) / 2, 3)


def sicaklikla_kalibre_et(
    olasilik_listesi: Sequence[Dict[str, float]],
    sicaklik: float,
) -> List[float]:
    """Verilen sıcaklıkla yeniden kalibre edilmiş güvenleri (max olasılık) döndürür."""
    sonuc: List[float] = []
    for olasilik in olasilik_listesi:
        sozde_logit = {k: math.log(max(v, 1e-12)) for k, v in olasilik.items()}
        p = softmax(sozde_logit, sicaklik)
        sonuc.append(max(p.values()) if p else 0.0)
    return sonuc


def kalibrasyon_raporu(
    guvenler: Sequence[float],
    dogrular: Sequence[bool],
    olasilik_listesi: Optional[Sequence[Dict[str, float]]] = None,
    dogru_siniflar: Optional[Sequence[str]] = None,
    kutu_sayisi: int = 10,
    sicaklik_ogren_izinli: bool = False,
) -> Dict[str, Any]:
    """Bir değerlendirme seti için tam kalibrasyon karnesi.

    `sicaklik_ogren_izinli=True` (yalnızca geliştirme setinde) ise ayrıca
    öğrenilen sıcaklık ve kalibrasyon sonrası ECE raporlanır. Held-out
    setlerde bu bayrak False tutulur (yalnızca ölçüm; bütünlük korunur).
    """
    em = ece_mce(guvenler, dogrular, kutu_sayisi)
    rk = risk_kapsama(guvenler, dogrular)
    rapor: Dict[str, Any] = {
        "n": len(guvenler),
        "ece": em["ece"],
        "mce": em["mce"],
        "brier": brier_skoru(guvenler, dogrular),
        "aurc": rk["aurc"],
        "reliability_kutulari": em["kutular"],
    }
    if (
        sicaklik_ogren_izinli
        and olasilik_listesi
        and dogru_siniflar
        and len(olasilik_listesi) == len(dogrular)
    ):
        T = sicaklik_ogren(olasilik_listesi, dogru_siniflar)
        kalibre_guven = sicaklikla_kalibre_et(olasilik_listesi, T)
        em2 = ece_mce(kalibre_guven, dogrular, kutu_sayisi)
        rapor["ogrenilen_sicaklik"] = T
        rapor["ece_kalibrasyon_sonrasi"] = em2["ece"]
    return rapor
