"""
Kurum Kokpiti — toplu evrak işleme istatistikleri (saf fonksiyonlar).

Uçtan uca pipeline'ın ürettiği sonuç sözlükleri listesinden, kurum
yönetiminin bir bakışta okuyabileceği özet göstergeler üretir:
tür/birim dağılımı, eksik bilgili evrak oranı, kritik eksiklik sayısı,
işlem süreleri ve tahmini zaman tasarrufu.

Şartname Referansı:
    - Görev 1: "Evrak Sınıflandırma ve İçerik Analizi" → tür dağılımı,
      eksik bilgi istatistikleri kurumsal izleme için özetlenir.
    - Görev 2: "Birim Yönlendirme" → birim dağılımı yönetim gösterge
      paneline taşınır.
    - "Gerçek zamana yakın çalışma" → toplu işlem süreleri raporlanır.

Tasarım:
    Bu modüldeki fonksiyonlar SAFTIR: girdi olarak sonuç sözlükleri alır,
    çıktı olarak sözlük döndürür; dosya/ağ/arayüz yan etkisi yoktur.
    Eksik anahtarlara ve bozuk kayıtlara toleranslıdır (dashboard bir
    kayıt yüzünden düşmemelidir).

Dürüstlük notu (tahmini tasarruf):
    Evrak başına manuel işlem süresi (MANUEL_ISLEM_DAKIKA_VARSAYIMI)
    resmî bir kaynağa dayanmayan, makul bir ÇALIŞMA VARSAYIMIDIR;
    yalnızca tasarruf potansiyelini görselleştirmek için kullanılır ve
    arayüzde de varsayım olduğu açıkça belirtilir.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kamu_evrak_ajan.kokpit")

# Evrak başına manuel işlem süresi varsayımı (dakika).
# VARSAYIMDIR, KAYNAK DEĞİLDİR: bir memurun bir evrakı okuma, türünü
# belirleme, bilgileri çıkarma, havale ve cevap taslağı hazırlama
# adımlarının tamamı için kabul edilen kaba bir ortalamadır. Gerçek süre
# kuruma ve evrak karmaşıklığına göre değişir; gösterge yalnızca
# karşılaştırma amaçlıdır.
MANUEL_ISLEM_DAKIKA_VARSAYIMI = 12


def _guvenli_sozluk(kayit: Any) -> dict:
    """Kaydı sözlüğe indirger; sözlük değilse boş sözlük döndürür."""
    return kayit if isinstance(kayit, dict) else {}


def _kritik_eksik_var_mi(eksikler: Any) -> bool:
    """Eksik bilgi listesinde 'kritik' öncelikli en az bir kayıt var mı?"""
    if not isinstance(eksikler, (list, tuple)):
        return False
    for eksik in eksikler:
        if isinstance(eksik, dict):
            if str(eksik.get("oncelik", "")).strip().lower() == "kritik":
                return True
    return False


def kokpit_ozeti(sonuclar: "list[dict]") -> dict:
    """
    Pipeline sonuç listesinden kurum kokpiti özet istatistikleri üretir.

    Args:
        sonuclar: EndToEndPipeline.process/process_batch çıktısı sözlükler.
            Eksik anahtarlı veya sözlük olmayan kayıtlar tolere edilir.

    Returns:
        Özet sözlüğü:
        {
            "evrak_sayisi": int,
            "tur_dagilimi": {tur_adi: adet},
            "birim_dagilimi": {birim: adet},
            "eksikli_evrak_orani": float (0-1),
            "kritik_eksikli_sayisi": int,
            "ort_islem_suresi_sn": float,
            "toplam_islem_suresi_sn": float,
            "dusuk_guvenli_sayisi": int,   # insan_onayi.gerekli işaretli evrak
            "tahmini_tasarruf": {
                "manuel_dakika_varsayimi": int,   # bkz. modül dürüstlük notu
                "manuel_toplam_saat": float,
                "sistem_toplam_saniye": float,
                "tasarruf_orani": float (0-1),
            },
        }
    """
    if not isinstance(sonuclar, (list, tuple)):
        logger.warning("kokpit_ozeti: liste beklenirken %s alındı.", type(sonuclar).__name__)
        sonuclar = []

    evrak_sayisi = len(sonuclar)
    tur_dagilimi: dict = {}
    birim_dagilimi: dict = {}
    eksikli_sayisi = 0
    kritik_eksikli_sayisi = 0
    dusuk_guvenli_sayisi = 0
    toplam_sure = 0.0

    for kayit in sonuclar:
        sonuc = _guvenli_sozluk(kayit)

        # Tür dağılımı (okunur ad tercih edilir; yoksa anahtar; yoksa Bilinmiyor)
        sinif = _guvenli_sozluk(sonuc.get("siniflandirma"))
        tur = str(sinif.get("tur_adi") or sinif.get("tur") or "Bilinmiyor").strip() or "Bilinmiyor"
        tur_dagilimi[tur] = tur_dagilimi.get(tur, 0) + 1

        # Birim dağılımı
        yonlendirme = _guvenli_sozluk(sonuc.get("yonlendirme"))
        birim = str(yonlendirme.get("birim") or "Belirsiz").strip() or "Belirsiz"
        birim_dagilimi[birim] = birim_dagilimi.get(birim, 0) + 1

        # Eksik bilgi istatistikleri
        eksikler = sonuc.get("eksik_bilgiler")
        if isinstance(eksikler, (list, tuple)) and len(eksikler) > 0:
            eksikli_sayisi += 1
            if _kritik_eksik_var_mi(eksikler):
                kritik_eksikli_sayisi += 1

        # Düşük güven / insan onayı işareti (Kapı 3 çıktısı)
        insan_onayi = _guvenli_sozluk(sonuc.get("insan_onayi"))
        if insan_onayi.get("gerekli") is True:
            dusuk_guvenli_sayisi += 1

        # İşlem süresi
        sure = sonuc.get("islem_suresi_saniye")
        try:
            toplam_sure += float(sure)
        except (TypeError, ValueError):
            pass

    eksikli_oran = (eksikli_sayisi / evrak_sayisi) if evrak_sayisi else 0.0
    ort_sure = (toplam_sure / evrak_sayisi) if evrak_sayisi else 0.0

    # Tahmini tasarruf — manuel süre bir VARSAYIMDIR (modül docstring'i)
    manuel_toplam_dakika = evrak_sayisi * MANUEL_ISLEM_DAKIKA_VARSAYIMI
    manuel_toplam_saniye = manuel_toplam_dakika * 60.0
    if manuel_toplam_saniye > 0:
        tasarruf_orani = 1.0 - (toplam_sure / manuel_toplam_saniye)
        tasarruf_orani = max(0.0, min(1.0, tasarruf_orani))
    else:
        tasarruf_orani = 0.0

    return {
        "evrak_sayisi": evrak_sayisi,
        "tur_dagilimi": tur_dagilimi,
        "birim_dagilimi": birim_dagilimi,
        "eksikli_evrak_orani": round(eksikli_oran, 3),
        "kritik_eksikli_sayisi": kritik_eksikli_sayisi,
        "ort_islem_suresi_sn": round(ort_sure, 3),
        "toplam_islem_suresi_sn": round(toplam_sure, 3),
        "dusuk_guvenli_sayisi": dusuk_guvenli_sayisi,
        "tahmini_tasarruf": {
            "manuel_dakika_varsayimi": MANUEL_ISLEM_DAKIKA_VARSAYIMI,
            "manuel_toplam_saat": round(manuel_toplam_dakika / 60.0, 2),
            "sistem_toplam_saniye": round(toplam_sure, 2),
            "tasarruf_orani": round(tasarruf_orani, 4),
        },
    }


def kokpit_iliskiler(sonuclar: "list[dict]") -> dict:
    """
    Toplu işlenen evraklar arasındaki ilişki zincirlerini döndürür.

    Kurum kokpitinin 'evrak ilişkileri' göstergesi: dilekçe → cevap →
    itiraz gibi yazışma zincirlerini İlgi referansları ve konu/taraf
    benzerliğinden otomatik kurar (bkz. src/utils/iliski_zinciri modül
    docstring'i — sinyal gerekçeleri orada).

    İlişki modülü tembel (lazy) import edilir: kokpit_ozeti kullanan
    mevcut çağrılar iliski_zinciri modülünü yüklemek zorunda kalmaz ve
    olası bir import hatası kokpitin diğer göstergelerini düşürmez.

    Args:
        sonuclar: EndToEndPipeline.process/process_batch çıktısı sözlükler.

    Returns:
        zincir_kur sözleşmesiyle aynı: {"zincirler": [...], "bagimsiz": [...]}.
    """
    from src.utils.iliski_zinciri import zincir_kur

    return zincir_kur(sonuclar)
