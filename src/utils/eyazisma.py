"""
e-Yazışma uyumlu üstveri TASLAĞI üretici.

DÜRÜST İFADE: Bu modül, Cumhurbaşkanlığı Dijital Dönüşüm Ofisi (CBDDO)
e-Yazışma Paketi yapısından ESİNLENEN, EBYS entegrasyon vizyonunu
gösteren bir üstveri TASLAĞI üretir; resmî e-Yazışma şeması (ustveri.xml,
paket bileşenleri, e-imza/şifreleme katmanları) birebir uygulanmamıştır.
Amaç, pipeline çıktısının bir EBYS'ye aktarılabilir yapıda özetlenmesini
kavram kanıtı olarak göstermektir.

Şartname Referansı:
    - Görev 2: "Resmî Yazı Taslaklama ve Birim Yönlendirme" → üretilen
      taslak ve yönlendirme kararının kurumsal sistemlere (EBYS) makine
      okunur üstveriyle taşınabileceğini gösterir.

Alan gerekçeleri (resmî yazışma gerçekliğine dayanır):
    - konu / muhatap / ilgi / dağıtım: Resmî Yazışmalarda Uygulanacak
      Usul ve Esaslar Hakkında Yönetmelik'in tanımladığı temel yazı
      bölümleridir.
    - guvenlik_kodu: yazının gizlilik derecesi; kurgusal demo evraklarında
      gizlilik işareti bulunmadığından varsayılan "TSD" (tasnif dışı)
      kullanılır.
    - ivedilik: yazının öncelik derecesi (normal/ivedi vb.); pipeline'ın
      önceliklendirme sonucu varsa oradan alınır.

Tasarım:
    uret_ustveri saf bir fonksiyondur; eksik anahtarlara toleranslıdır
    (boş sonuç sözlüğünden bile geçerli bir taslak üretir).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger("kamu_evrak_ajan.eyazisma")

# Üstveri taslağı sürümü — resmî e-Yazışma sürümleriyle karışmaması için
# açıkça "taslak" öneki taşır.
USTVERI_SURUMU = "taslak-0.1"

# Varsayılan gizlilik derecesi: tasnif dışı (gizlilik işareti taşımayan yazı)
VARSAYILAN_GUVENLIK_KODU = "TSD"

KAYNAK_SISTEM = "Kamu Evrak Akilli Ajan"


def _sozluk(deger: Any) -> dict:
    """Değeri sözlüğe indirger; sözlük değilse boş sözlük döndürür."""
    return deger if isinstance(deger, dict) else {}


def _metin_listesi(deger: Any) -> list:
    """Değeri temiz metin listesine indirger (liste değilse boş liste)."""
    if not isinstance(deger, (list, tuple)):
        return []
    ogeler = []
    for oge in deger:
        metin = str(oge).strip() if not isinstance(oge, dict) else str(
            oge.get("ad") or oge.get("birim") or oge.get("metin") or ""
        ).strip()
        if metin:
            ogeler.append(metin)
    return ogeler


def uret_ustveri(sonuc: dict) -> dict:
    """
    Pipeline sonucundan e-Yazışma'dan esinlenen üstveri TASLAĞI üretir.

    Args:
        sonuc: EndToEndPipeline.process çıktısı sözlüğü. Eksik anahtarlar
            tolere edilir; sözlük dışı girdi boş sözlük gibi işlenir.

    Returns:
        Üstveri taslağı sözlüğü:
        {
            "ustveri_surumu": "taslak-0.1",
            "belge": {"konu", "tur", "tur_adi", "olusturma_tarihi",
                      "guvenlik_kodu", "ivedilik"},
            "muhatap": {"ad", "belirlendi"},
            "ilgi_listesi": [...],
            "dagitim": [...],
            "yonlendirme": {"birim", "birim_kodu", "guven"},
            "eksik_alanlar": [...],
            "kaynak_sistem": "Kamu Evrak Akilli Ajan",
        }
    """
    sonuc = _sozluk(sonuc)
    sinif = _sozluk(sonuc.get("siniflandirma"))
    bilgi = _sozluk(sonuc.get("bilgi_cikarim"))
    yonlendirme = _sozluk(sonuc.get("yonlendirme"))
    onceliklendirme = _sozluk(sonuc.get("onceliklendirme"))

    muhatap_adi = str(bilgi.get("muhatap") or "").strip()

    eksik_alanlar = []
    for eksik in sonuc.get("eksik_bilgiler") or []:
        if isinstance(eksik, dict):
            alan = str(eksik.get("alan") or "").strip()
            if alan:
                eksik_alanlar.append(alan)
        elif str(eksik).strip():
            eksik_alanlar.append(str(eksik).strip())

    ustveri = {
        "ustveri_surumu": USTVERI_SURUMU,
        "belge": {
            "konu": str(bilgi.get("konu") or "").strip(),
            "tur": str(sinif.get("tur") or "").strip(),
            "tur_adi": str(sinif.get("tur_adi") or "").strip(),
            # Üstverinin (taslağın) üretildiği gün — evrak tarihi değildir
            "olusturma_tarihi": date.today().isoformat(),
            "guvenlik_kodu": VARSAYILAN_GUVENLIK_KODU,
            "ivedilik": str(onceliklendirme.get("oncelik") or "normal").strip() or "normal",
        },
        "muhatap": {
            "ad": muhatap_adi,
            "belirlendi": bool(muhatap_adi),
        },
        "ilgi_listesi": _metin_listesi(bilgi.get("ilgi_referanslari")),
        "dagitim": _metin_listesi(bilgi.get("dagitim_birimleri")),
        "yonlendirme": {
            "birim": str(yonlendirme.get("birim") or "").strip(),
            "birim_kodu": str(yonlendirme.get("birim_kodu") or "").strip(),
            "guven": yonlendirme.get("guven"),
        },
        "eksik_alanlar": eksik_alanlar,
        "kaynak_sistem": KAYNAK_SISTEM,
    }
    logger.debug("e-Yazışma üstveri taslağı üretildi (tür=%s).", ustveri["belge"]["tur"])
    return ustveri
