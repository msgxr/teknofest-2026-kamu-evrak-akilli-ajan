"""Split conformal prediction — kapsama-garantili tahmin kümeleri.

Tekil-etiket kararı yerine, dağılımdan-bağımsız bir KAPSAMA GARANTİSİ (ör. %90)
veren tahmin KÜMELERİ üretir: kalibrasyon dilimindeki uygunsuzluk (nonconformity)
skorlarının düzeltilmiş kuantili bir eşik belirler; test evrağında bu eşiği geçen
tüm sınıflar kümeye alınır. Küme tek elemanlıysa karar otomatik akar; birden çok
tür içeriyorsa "belirsiz" işaretiyle insan onayına düşer — böylece HITL eşiği
keyfî 0,6 yerine İSTATİSTİKSEL kapsama garantisine dayanır.

Yöntem: LAC (Least Ambiguous set-valued Classifier) uygunsuzluk skoru
s = 1 − p(gerçek sınıf). Eşik, kalibrasyon skorlarının ceil((n+1)(1−α))/n
ampirik kuantilidir (Vovk; Sadinle vd. 2019). Ampirik kapsama ≈ 1−α olmalıdır.

Literatür: Angelopoulos & Bates (2021) "A Gentle Introduction to Conformal
Prediction"; Sadinle, Lei, Wasserman (2019) LAC. Saf Python; offline-first.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence


def uygunsuzluk_skorlari(
    olasiliklar: Sequence[Dict[str, float]], dogru_siniflar: Sequence[str]
) -> List[float]:
    """LAC uygunsuzluk skoru: her örnek için 1 − p(gerçek sınıf). Yüksek = kötü."""
    return [
        1.0 - float(p.get(dogru, 0.0))
        for p, dogru in zip(olasiliklar, dogru_siniflar)
    ]


def konformal_esik(skorlar: Sequence[float], alfa: float = 0.1) -> float:
    """Kalibrasyon skorlarının (1−α) düzeltilmiş ampirik kuantil eşiği.

    Kapsama garantisi için indeks ceil((n+1)(1−α)); n küçükse eşik 1.0'a
    doyurulur (her sınıfı kümeye alır → garanti korunur).
    """
    n = len(skorlar)
    if n == 0:
        return 1.0
    k = math.ceil((n + 1) * (1 - alfa))
    if k >= n:
        return 1.0  # düzeltme n'i aşıyor → tam kapsama (muhafazakâr)
    return sorted(skorlar)[k - 1]


def tahmin_kumesi(olasilik: Dict[str, float], esik: float) -> List[str]:
    """Uygunsuzluğu eşiği geçmeyen (p ≥ 1−eşik) sınıfların kümesi.

    Küme boş çıkarsa en yüksek olasılıklı sınıf tek başına alınır (boş küme
    kararsızlığını önler)."""
    kume = [s for s, p in olasilik.items() if (1.0 - float(p)) <= esik]
    if not kume and olasilik:
        kume = [max(olasilik, key=olasilik.get)]
    return sorted(kume)


def konformal_degerlendirme(
    olasiliklar: Sequence[Dict[str, float]],
    dogru_siniflar: Sequence[str],
    alfa: float = 0.1,
) -> Dict[str, Any]:
    """Split conformal karnesi: eşik + ampirik kapsama + ortalama küme boyutu.

    NOT: Bu değerlendirme transdüktif (aynı set üzerinde eşik + ölçüm) yapılır;
    held-out setlerde yalnızca RAPORLAMA amaçlıdır (kural/kod tuning YAPILMAZ,
    değerlendirme bütünlüğü korunur). Ampirik kapsama hedef 1−α'ya yakın olmalı.
    """
    n = len(olasiliklar)
    if n == 0:
        return {"alfa": alfa, "hedef_kapsama": round(1 - alfa, 4), "n": 0}
    skorlar = uygunsuzluk_skorlari(olasiliklar, dogru_siniflar)
    esik = konformal_esik(skorlar, alfa)
    kumeler = [tahmin_kumesi(p, esik) for p in olasiliklar]
    kapsanan = sum(1 for k, d in zip(kumeler, dogru_siniflar) if d in k)
    tekil = sum(1 for k in kumeler if len(k) == 1)
    return {
        "alfa": alfa,
        "hedef_kapsama": round(1 - alfa, 4),
        "esik": round(esik, 4),
        "ampirik_kapsama": round(kapsanan / n, 4),
        "ortalama_kume_boyutu": round(sum(len(k) for k in kumeler) / n, 4),
        "tekil_kume_orani": round(tekil / n, 4),
        "n": n,
    }
