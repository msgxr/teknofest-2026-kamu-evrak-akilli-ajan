# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Özet kalitesi ölçümü ve muhafazakâr cümle sıkıştırma (extract-then-compress).

Şartname "özetleme kalitesi"ni açıkça puanlar (Uygulama). Altın (referans) özet
bulunmadığından bu modül REFERANSSIZ ama anlamlı metrikler sağlar:
  - sadakat (faithfulness): özetteki sayı/tarih olgularının kaynakta bulunması
    (halüsinasyon yokluğu). Düşükse özet kaynakta olmayan bilgi uydurmuştur.
  - kaynak-kapsama (content coverage): kaynaktaki sayı/tarih olgularının özette
    temsili (bilgi tamlığı).
  - sıkıştırma oranı: özet uzunluğu / kaynak uzunluğu.
Ayrıca `rouge_l` yardımcı fonksiyonu, altın özet mevcutsa ROUGE-L F1 hesaplar.

`sadelestir`, extractive özete uygulanan muhafazakâr cümle sıkıştırmasıdır:
sayı/tarih İÇERMEYEN parantez içi açıklamaları ve baştaki doldurucu bağlaçları
atar; sayı/mevzuat referansı taşıyan parantezlere DOKUNMAZ (sadakat korunur).

Literatür: Chen & Bansal (2018) extract-then-abstract; Lin (2004) ROUGE;
faithfulness/groundedness özet değerlendirmesi (RAGAS/summarization). Saf Python.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

# Sayı / tarih / mevzuat-no benzeri diziler (özetin sadakatini ölçmede
# "olgu" olarak kullanılır — halüsinasyon en çok bunlarda görülür).
_OLGU = re.compile(r"\d[\d.,/:\-]*\d|\d")

# Baştaki doldurucu bağlaçlar (anlam taşımaz).
_DOLDURUCU = re.compile(
    r"^(ayrıca|bununla birlikte|bu bağlamda|ilaveten|öte yandan|ancak|fakat)[,\s]+",
    re.IGNORECASE,
)


def _olgular(metin: str) -> set:
    """Metindeki sayı/tarih olgularının kümesi."""
    return {m.group() for m in _OLGU.finditer(metin or "")}


def sadakat(ozet: str, kaynak: str) -> float:
    """Özetteki sayı/tarih olgularının kaynakta bulunma oranı [0-1].

    1.0 = tüm sayısal olgular kaynağa dayanıyor (halüsinasyon yok). Özet hiç
    olgu içermiyorsa 1.0 (uydurma riski yok).
    """
    o = _olgular(ozet)
    if not o:
        return 1.0
    k = _olgular(kaynak)
    return round(sum(1 for x in o if x in k) / len(o), 4)


def kaynak_kapsama(ozet: str, kaynak: str) -> Optional[float]:
    """Kaynaktaki sayı/tarih olgularının özette temsil oranı [0-1].

    Kaynak hiç olgu içermiyorsa None (metriğe katılmaz).
    """
    k = _olgular(kaynak)
    if not k:
        return None
    o = _olgular(ozet)
    return round(sum(1 for x in k if x in o) / len(k), 4)


def sikistirma_orani(ozet: str, kaynak: str) -> float:
    """Özet uzunluğu / kaynak uzunluğu (kelime bazında). Düşük = daha sıkı."""
    kaynak_uzunluk = len((kaynak or "").split())
    ozet_uzunluk = len((ozet or "").split())
    return round(ozet_uzunluk / kaynak_uzunluk, 4) if kaynak_uzunluk else 0.0


def _lcs_uzunluk(a: list, b: list) -> int:
    """En uzun ortak alt dizi (LCS) uzunluğu — ROUGE-L için."""
    if not a or not b:
        return 0
    onceki = [0] * (len(b) + 1)
    for x in a:
        simdiki = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            simdiki[j] = onceki[j - 1] + 1 if x == y else max(onceki[j], simdiki[j - 1])
        onceki = simdiki
    return onceki[len(b)]


def rouge_l(aday: str, referans: str) -> float:
    """ROUGE-L F1 (LCS tabanlı). Altın (referans) özet mevcutsa kullanılır.

    Literatür: Lin (2004). Referanssız değerlendirmede sadakat/kapsama tercih
    edilir; bu fonksiyon altın özet elde edildiğinde hazır olması için sağlanır.
    """
    a = (aday or "").split()
    r = (referans or "").split()
    if not a or not r:
        return 0.0
    lcs = _lcs_uzunluk(a, r)
    p = lcs / len(a)
    rec = lcs / len(r)
    return round(2 * p * rec / (p + rec), 4) if (p + rec) else 0.0


def sadelestir(cumle: str) -> str:
    """Muhafazakâr cümle sıkıştırma (extract-then-compress).

    - Sayı/mevzuat-no İÇERMEYEN parantez içi açıklamaları atar (sayı içeren
      parantezlere dokunmaz — mevzuat referansı/tarih korunur → sadakat).
    - Baştaki doldurucu bağlaçları atar.
    Anlamı ve sayısal olguları korur.
    """
    if not cumle:
        return cumle

    def _parantez(m: "re.Match") -> str:
        return m.group(0) if re.search(r"\d", m.group(1)) else ""

    c = re.sub(r"\s*\(([^)]*)\)", _parantez, cumle)
    c = _DOLDURUCU.sub("", c)
    return re.sub(r"\s+", " ", c).strip()


def sadelestir_guvenli(cumle: str) -> str:
    """`sadelestir` uygular; ancak bir sayı/tarih olgusu düşerse orijinal
    cümleyi korur (sadakat garantisi — extractive özette güvenli kullanım)."""
    sade = sadelestir(cumle)
    if sade and _olgular(sade) == _olgular(cumle):
        return sade
    return cumle


def ozet_kalite_raporu(ozet: str, kaynak: str) -> Dict[str, object]:
    """Bir evrak için referanssız özet kalite karnesi."""
    return {
        "sadakat": sadakat(ozet, kaynak),
        "kaynak_kapsama": kaynak_kapsama(ozet, kaynak),
        "sikistirma_orani": sikistirma_orani(ozet, kaynak),
    }
