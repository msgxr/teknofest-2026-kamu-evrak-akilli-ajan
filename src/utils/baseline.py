# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Saf baseline sınıflandırıcı — ablasyon ve 'İkiz Ekran' karşılaştırması için.

Bilerek ZAYIF ama ADİL bir referans: yalnızca anahtar-kelime sayımı, en çok
eşleşen türü seçer; kalibrasyon, güven skoru, ensemble, reddetme (reject option)
ve koşullu kapılar YOKTUR. Amaç, tam 11-ajan sistemin bu güvence katmanlarıyla
kattığı değeri NİCEL göstermektir (McNemar ile 'anlamlı iyileşme' kanıtı) ve
jürinin "sizinki saf-keyword'e göre neden daha iyi?" sorusunu tek ekranda
görsel/istatistiksel yanıtlamaktır ('İkiz Ekran' demosu).

Şeffaflık/etik: baseline'ın zayıflığı KASITLI ve ADİL kurulmuştur; tanımı
demoda/raporda açıkça belirtilir (samankukla tuzağından kaçınma). Saf Python.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Her tür için ayırt edici anahtar kelimeler (sözcük-başı, küçük harf).
# Kasıtlı olarak sade: yapısal sinyal, checksum, morfoloji vб. YOK.
BASELINE_ANAHTARLAR: Dict[str, List[str]] = {
    "dilekce": ["dilekçe", "arz ederim", "talep ediyorum", "başvuru", "rica ediyorum"],
    "ust_yazi": ["üst yazı", "gereğini", "rica ederim", "yazımız ekinde"],
    "cevap_yazisi": ["cevaben", "ilgi yazı", "yazınıza", "cevabıdır", "ilgide kayıtlı"],
    "tutanak": ["tutanak", "komisyon", "imza altına", "düzenlenmiştir"],
    "rapor": ["rapor", "bulgu", "sonuç ve", "değerlendirme", "inceleme sonucunda"],
    "genelge": ["genelge", "duyurulur", "tüm birimlere", "genelgesi"],
    "onayli_belge": ["olur", "makam onay", "onaylanmıştır", "oluru"],
    "bilgilendirme": ["bilgilendirme", "bilgilerinize", "duyuru", "bilgi notu"],
}


def baseline_siniflandir(metin: str) -> Tuple[str, int]:
    """Anahtar-kelime sayımıyla tür tahmini (güven YOK).

    Returns:
        (tur, eslesme_sayisi) — hiç eşleşme yoksa ("diger", 0).
    """
    dusuk = (metin or "").lower()
    sayimlar: Dict[str, int] = {}
    for tur, anahtarlar in BASELINE_ANAHTARLAR.items():
        sayimlar[tur] = sum(1 for a in anahtarlar if a in dusuk)
    en_iyi = max(sayimlar, key=lambda t: sayimlar[t])
    if sayimlar[en_iyi] == 0:
        return "diger", 0
    return en_iyi, sayimlar[en_iyi]
