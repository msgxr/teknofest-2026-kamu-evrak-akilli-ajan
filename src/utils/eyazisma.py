# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

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

from src.utils.sayi_uretici import sayi_uret
from src.utils.yazisma_desenleri import (
    belge_konusu,
    belge_sayisi,
    belge_tarihi,
    gizlilik_damgasi,
)

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


def uret_ustveri(sonuc: dict, belge_metni: str = "") -> dict:
    """
    Pipeline sonucundan e-Yazışma'dan esinlenen üstveri TASLAĞI üretir.

    Args:
        sonuc: EndToEndPipeline.process çıktısı sözlüğü. Eksik anahtarlar
            tolere edilir; sözlük dışı girdi boş sözlük gibi işlenir.
        belge_metni: Üstverinin ait olduğu belge (taslak) metni. Verilirse
            Sayı/Konu/tarih değerleri ve gizlilik damgası DOĞRUDAN belge
            görüntüsünden okunur — Yönetmelik m.28/3 ilkesi ("belge
            görüntüsü üzerinde yer alan bilgiler ile üstveride yer alan
            bilgiler arasında fark olamaz") tasarımla garanti edilir.

    Returns:
        Üstveri taslağı sözlüğü:
        {
            "ustveri_surumu": "taslak-0.1",
            "belge": {"konu", "tur", "tur_adi", "olusturma_tarihi",
                      "sayi", "belge_tarihi", "sayi_onerisi",
                      "guvenlik_kodu", "ivedilik"},
            "muhatap": {"ad", "belirlendi"},
            "ilgi_listesi": [...],
            "dagitim": [...],
            "yonlendirme": {"birim", "birim_kodu", "guven"},
            "eksik_alanlar": [...],
            "kaynak_sistem": "Kamu Evrak Akilli Ajan",
        }
        "sayi" ve "belge_tarihi" belge görüntüsünden BİREBİR alınır (m.28/3
        kapsamı); "sayi_onerisi" ise belgede YER ALMAYAN, EBYS'nin
        vereceği biçimin kurgu örneğidir (tutarlılık kapsamına girmez).
    """
    sonuc = _sozluk(sonuc)
    sinif = _sozluk(sonuc.get("siniflandirma"))
    bilgi = _sozluk(sonuc.get("bilgi_cikarim"))
    yonlendirme = _sozluk(sonuc.get("yonlendirme"))
    onceliklendirme = _sozluk(sonuc.get("onceliklendirme"))

    muhatap_adi = str(bilgi.get("muhatap") or "").strip()

    # m.28/3: belge görüntüsündeki değerler üstveriye BİREBİR taşınır
    belge_metni = str(belge_metni or "")
    belge_sayi = belge_sayisi(belge_metni)
    belge_konu = belge_konusu(belge_metni)
    belge_tarih = belge_tarihi(belge_metni)
    damga = gizlilik_damgasi(belge_metni)
    guvenlik_kodu = damga or VARSAYILAN_GUVENLIK_KODU

    eksik_alanlar = []
    for eksik in sonuc.get("eksik_bilgiler") or []:
        if isinstance(eksik, dict):
            alan = str(eksik.get("alan") or "").strip()
            if alan:
                eksik_alanlar.append(alan)
        elif str(eksik).strip():
            eksik_alanlar.append(str(eksik).strip())

    evrak_turu = str(sinif.get("tur") or "").strip()
    ustveri = {
        "ustveri_surumu": USTVERI_SURUMU,
        "belge": {
            # m.28/3 kapsamı: belge görüntüsünden BİREBİR okunan alanlar
            # (belge_metni verilmediyse çıkarım sonuçlarına düşülür)
            "konu": belge_konu or str(bilgi.get("konu") or "").strip(),
            "sayi": belge_sayi,
            "belge_tarihi": belge_tarih,
            "tur": evrak_turu,
            "tur_adi": str(sinif.get("tur_adi") or "").strip(),
            # Üstverinin (taslağın) üretildiği gün — evrak tarihi değildir
            "olusturma_tarihi": date.today().isoformat(),
            # Belgede YER ALMAYAN öneri alanı: EBYS'nin vereceği m.11
            # biçiminin kurgu örneği (tutarlılık denetimi kapsamı dışı)
            "sayi_onerisi": sayi_uret(
                str(yonlendirme.get("birim") or "Kurgu Kurum"), evrak_turu
            ),
            "guvenlik_kodu": guvenlik_kodu,
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


def uret_ustveri_xml(sonuc: dict, belge_metni: str = "") -> str:
    """e-Yazışma Paketi / TS 13298 tarzı üstveri XML'i üretir (stdlib xml).

    Resmî e-Yazışma Paketi'nin temel üstveri elemanlarını (Konu, BelgeTarihi,
    Tür, GüvenlikKodu, İvedilik, Muhatap, İlgiListesi, DağıtımListesi) XML olarak
    modeller; kurum EBYS'lerine standart-yakın aktarım için bir köprüdür.

    DÜRÜSTLÜK / KAPSAM: Bu bir üstveri ÖRNEĞİDİR. e-imza, şifreleme ve tam paket
    imzalama KAPSAM DIŞIDIR; resmî şema doğrulaması (XSD) için CBDDO e-Yazışma
    Teknik Rehberi esastır. Kaçınılan sahte kesinlik: numaralar/DETSIS gerçek
    değil, kurgu ÖNERİdir (belge tutarlılık denetimi kapsamı dışı alanlar).

    Literatür/Kaynak: e-Yazışma Teknik Rehberi (CBDDO); TS 13298 EBYS standardı.
    """
    import xml.etree.ElementTree as ET

    ustveri = uret_ustveri(sonuc, belge_metni)
    belge = _sozluk(ustveri.get("belge"))
    muhatap = _sozluk(ustveri.get("muhatap"))

    kok = ET.Element("Ustveri", {
        "surum": str(ustveri.get("ustveri_surumu", "")),
        "kaynak": str(ustveri.get("kaynak_sistem", "")),
    })
    belge_ge = ET.SubElement(kok, "Belge")
    ET.SubElement(belge_ge, "Konu").text = str(belge.get("konu", ""))
    ET.SubElement(belge_ge, "BelgeTarihi").text = str(belge.get("belge_tarihi") or "")
    ET.SubElement(belge_ge, "Tur").text = str(belge.get("tur", ""))
    ET.SubElement(belge_ge, "GuvenlikKodu").text = str(belge.get("guvenlik_kodu") or "")
    ET.SubElement(belge_ge, "Ivedilik").text = str(belge.get("ivedilik", "normal"))
    ET.SubElement(belge_ge, "SayiOnerisi").text = str(belge.get("sayi_onerisi", ""))

    muhatap_ge = ET.SubElement(kok, "Muhatap")
    ET.SubElement(muhatap_ge, "Ad").text = str(muhatap.get("ad", ""))

    ilgi_ge = ET.SubElement(kok, "IlgiListesi")
    for ilgi in _metin_listesi(ustveri.get("ilgi_listesi")):
        ET.SubElement(ilgi_ge, "Ilgi").text = str(ilgi)

    dagitim_ge = ET.SubElement(kok, "DagitimListesi")
    for hedef in _metin_listesi(ustveri.get("dagitim")):
        ET.SubElement(dagitim_ge, "Dagitim").text = str(hedef)

    return ET.tostring(kok, encoding="unicode")


def ustveri_belge_tutarliligi(ustveri: dict, belge_metni: str) -> dict:
    """
    Üstveri ↔ belge görüntüsü BİREBİR eşitlik denetimi (m.28/3 otomasyonu).

    Yönetmelik m.28/3: "Üstveri elemanları belgenin ayrılmaz bir
    bütünüdür. Tarih ve sayı gibi belge görüntüsü üzerinde yer alan
    bilgiler ile üstveride yer alan bilgiler arasında fark olamaz."
    Bu fonksiyon ilkeyi birim-testlenebilir bir denetime çevirir: belge
    metninden okunan Sayı/Konu/tarih/gizlilik değerleri, üstverideki
    karşılıklarıyla karşılaştırılır. Her iki tarafta da bulunmayan alan
    tutarlı sayılır ("fark" yoktur).

    Args:
        ustveri: uret_ustveri çıktısı
        belge_metni: Üstverinin ait olduğu belge (taslak) metni

    Returns:
        {"tutarli": bool, "dayanak": "Yön. (2646) m.28/3",
         "kontroller": [{"alan", "ustveri", "belge", "tutarli"}]}
    """
    ustveri = _sozluk(ustveri)
    belge = _sozluk(ustveri.get("belge"))
    metin = str(belge_metni or "")

    ciftler = [
        ("sayi", str(belge.get("sayi") or "").strip(), belge_sayisi(metin)),
        ("konu", str(belge.get("konu") or "").strip(), belge_konusu(metin)),
        ("belge_tarihi", str(belge.get("belge_tarihi") or "").strip(),
         belge_tarihi(metin)),
        ("guvenlik_kodu", str(belge.get("guvenlik_kodu") or "").strip(),
         gizlilik_damgasi(metin) or VARSAYILAN_GUVENLIK_KODU),
    ]

    kontroller = []
    for alan, ustveri_degeri, belge_degeri in ciftler:
        kontroller.append({
            "alan": alan,
            "ustveri": ustveri_degeri,
            "belge": belge_degeri,
            "tutarli": ustveri_degeri == belge_degeri,
        })

    return {
        "tutarli": all(k["tutarli"] for k in kontroller),
        "dayanak": "Yön. (2646) m.28/3",
        "kontroller": kontroller,
    }
