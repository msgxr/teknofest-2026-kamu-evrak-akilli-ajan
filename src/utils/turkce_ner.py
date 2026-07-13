# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Türkçe adlandırılmış varlık çıkarımı (NER) — gazetteer + kural tabanlı.

YER (lokasyon) varlıklarını saf Python ile birinci-sınıf olarak çıkarır:
Türkiye'nin 81 ili gazetteer'ı + "... İli/İlçesi/Belediyesi/Valiliği/
Kaymakamlığı/Bölge Müdürlüğü" desenleri. Mevcut sistemde yalnızca adres
tespiti vardı; bu katman "yer"i açık bir varlık türü olarak ekler
(şartname: "önemli bilgi unsurlarını çıkarma").

Kişi ve kurum çıkarımı hâlihazırda info_extraction_agent'ta yapılır; bu modül
onu YER boyutuyla tamamlar. Bu katman TAMAMEN kural tabanlıdır (hiçbir model
ağırlığı indirmez/gerektirmez). Gelecekte bir Türkçe NER modeli (ör. BERTurk
tabanlı) mevcut LLM-opsiyonel deseniyle bu katmanı zenginleştirebilir; böyle bir
model eklenirse ağırlık depoya KONMAZ, yalnızca `docs/model_bilgileri.md`'de
bağlantı + sürüm + lisans ile dokümante edilir (şartname m.7).

Literatür: gazetteer-tabanlı NER; CoNLL-2003 varlık-düzeyi değerlendirme
geleneği (altın etiket mevcutsa P/R/F1). Saf Python; offline-first korunur.
"""

from __future__ import annotations

import re
from typing import Dict, List

# Türkiye'nin 81 ili — yer gazetteer'ı çekirdeği (hepsi tek sözcük).
ILLER = frozenset({
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara",
    "Antalya", "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis",
    "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir",
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkâri", "Hatay", "Isparta",
    "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri",
    "Kırklareli", "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya",
    "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir", "Niğde",
    "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas",
    "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van",
    "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman", "Kırıkkale",
    "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük",
    "Kilis", "Osmaniye", "Düzce",
})

# Büyük harfle başlayan Türkçe sözcük
_KELIME = re.compile(r"[A-ZÇĞİÖŞÜ][a-zçğıöşüâîû]+")

# "X İli / İlçesi / Belediyesi / Valiliği / Kaymakamlığı / Bölge Müdürlüğü"
_YER_DESEN = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+"
    r"(İli|İlçesi|Belediyesi|Valiliği|Kaymakamlığı|Büyükşehir Belediyesi)"
)


def _tekillestir(ogeler: List[str]) -> List[str]:
    """Sırayı koruyarak benzersizleştirir."""
    gorulen = set()
    sonuc = []
    for o in ogeler:
        if o not in gorulen:
            gorulen.add(o)
            sonuc.append(o)
    return sonuc


def yer_cikar(metin: str) -> List[str]:
    """Metinden yer (lokasyon) varlıklarını çıkarır (il gazetteer + desen).

    1. 81 il gazetteer'ı (sözcük düzeyinde eşleşme),
    2. "X İli/İlçesi/Belediyesi..." desenleri.
    """
    if not metin:
        return []
    bulunanlar: List[str] = []
    for kelime in _KELIME.findall(metin):
        if kelime in ILLER:
            bulunanlar.append(kelime)
    for m in _YER_DESEN.finditer(metin):
        bulunanlar.append(f"{m.group(1)} {m.group(2)}")
    return _tekillestir(bulunanlar)


def varliklari_cikar(metin: str) -> Dict[str, List[str]]:
    """Yer varlıklarını çıkarır (kişi/kurum info_extraction_agent'tan gelir)."""
    return {"yerler": yer_cikar(metin)}


def varlik_f1(altin: List[str], tahmin: List[str]) -> Dict[str, float]:
    """CoNLL-tarzı varlık-düzeyi precision/recall/F1 (altın etiket mevcutsa).

    Şu an altın varlık etiketi bulunmadığından değerlendirmede kullanılmaz;
    altın küme elde edildiğinde hazır olması için sağlanır.
    """
    a = set(altin)
    t = set(tahmin)
    tp = len(a & t)
    p = tp / len(t) if t else 0.0
    r = tp / len(a) if a else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}
