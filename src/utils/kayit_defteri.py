# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Evrak Kayıt Defteri — SQLite tabanlı işlem denetim izi (audit trail).

Kamu evrak yönetiminde her evrak işlemi kayıt altına alınmak zorundadır:
Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik ve
Devlet Arşiv Hizmetleri mevzuatı, gelen/giden evrakın kayıt defterine
işlenmesini ve işlemlerin sonradan denetlenebilmesini gerektirir. Bu
modül, uçtan uca pipeline'ın ürettiği her işlem sonucunun özet künyesini
yerel bir SQLite veritabanına işleyerek bu "evrak kayıt defteri"
gerçekliğini sisteme taşır.

Şartname Referansı:
    - "Gerçek iş akışına uygunluk" → kamu kurumlarındaki evrak kayıt
      defteri / EBYS denetim izi pratiğinin karşılığıdır.
    - Görev 1 + Görev 2 çıktıları (tür, birim, öncelik, eksiklik,
      format skoru) tek satırlık denetim kaydında özetlenir.

Tasarım:
    - Yalnızca stdlib sqlite3 kullanılır; ek bağımlılık yoktur.
    - Her çağrıda kısa ömürlü bağlantı açılır/kapanır: SQLite bağlantısı
      iş parçacığına bağlıdır ve Streamlit her etkileşimi ayrı iş
      parçacığında çalıştırır; bağlantı saklamak bu ortamda hataya açıktır.
    - GÜVENLİK: tüm sorgular parametrelidir (SQL injection'a karşı,
      CWE-89); serbest metin araması LIKE joker karakterlerinden de
      arındırılır (ESCAPE), böylece kullanıcı girdisi desen değil
      düz metin olarak aranır.
    - Kayıt yazımı pipeline sonucunun eksik/bozuk alanlarına toleranslıdır:
      denetim izi, tek bir bozuk sonuç yüzünden kopmamalıdır.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kamu_evrak_ajan.kayit_defteri")

# Varsayılan veritabanı yolu (proje kökü/data/processed altında)
VARSAYILAN_DB_YOLU = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "processed" / "kayit_defteri.db"
)

# Serbest metin aramasında tek seferde döndürülecek azami kayıt sınırı;
# arayüzün tek sayfada makul biçimde gösterebileceği üst sınırdır.
_AZAMI_LIMIT = 500

# Emsal arama için saklanan evrak metni özünün karakter sınırı: BM25'in
# ayırt edici sözcükleri yakalaması için evrakın başı (konu, muhatap,
# talep) yeterlidir; tam metin saklamak defteri şişirir ve KVKK açısından
# gereksiz veri biriktirir (veri minimizasyonu).
METIN_OZU_KARAKTER = 2000

_TABLO_SQL = """
CREATE TABLE IF NOT EXISTS islemler (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman         TEXT NOT NULL,
    kaynak        TEXT,
    tur           TEXT,
    tur_guven     REAL,
    birim         TEXT,
    birim_guven   REAL,
    oncelik       TEXT,
    son_tarih     TEXT,
    eksik_sayisi  INTEGER,
    kritik_eksik  INTEGER,
    format_skoru  REAL,
    sure_saniye   REAL,
    insan_onayi   INTEGER,
    insan_onayi_gerekce TEXT,
    ozet_ilk_200  TEXT,
    metin_ozu     TEXT,
    yazi_turu     TEXT
)
"""

# Şema geçişi (migration) sütunları: eski sürümle oluşturulmuş defterlerde
# bulunmayan sütunlar bağlantı açılışında ALTER TABLE ile eklenir.
# Gerekçe: kayıt defteri kalıcı bir denetim izidir; kurulu bir sistemdeki
# db dosyası silinip yeniden oluşturulamaz. SQLite'ta ADD COLUMN mevcut
# satırları NULL bırakır — veri kaybı olmadan geriye uyumlu genişleme.
_GECIS_SUTUNLARI = {
    "metin_ozu": "TEXT",   # evrak metninin ilk ~2000 karakteri (emsal arama belgesi)
    "yazi_turu": "TEXT",   # üretilen yazı taslağının türü (örn. 'cevap_yazisi')
    # İnsan Onayı Kuyruğu: onay gerekçeleri ("; " ile birleştirilmiş metin)
    "insan_onayi_gerekce": "TEXT",
}


def _guvenli_sozluk(deger: Any) -> dict:
    """Değeri sözlüğe indirger; sözlük değilse boş sözlük döndürür."""
    return deger if isinstance(deger, dict) else {}


def _guvenli_sayi(deger: Any) -> Optional[float]:
    """Değeri float'a çevirir; çevrilemiyorsa None döndürür."""
    try:
        return float(deger)
    except (TypeError, ValueError):
        return None


def _kritik_eksik_var_mi(eksikler: Any) -> bool:
    """Eksik bilgi listesinde 'kritik' öncelikli en az bir kayıt var mı?"""
    if not isinstance(eksikler, (list, tuple)):
        return False
    for eksik in eksikler:
        if isinstance(eksik, dict):
            if str(eksik.get("oncelik", "")).strip().lower() == "kritik":
                return True
    return False


def _like_deseni(metin: str) -> str:
    """
    Serbest metni güvenli LIKE desenine çevirir.

    # GÜVENLİK: kullanıcı girdisindeki LIKE joker karakterleri (%, _)
    # ve kaçış karakteri (\\) etkisizleştirilir; girdi desen olarak değil
    # düz metin olarak aranır (sorguda ESCAPE '\\' ile birlikte kullanılır).
    """
    kacisli = (
        metin.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{kacisli}%"


class KayitDefteri:
    """
    Evrak işlem kayıt defteri (SQLite denetim izi).

    Her işlenen evrak için tek satırlık denetim kaydı tutar; kayıtlar
    tür/birim/öncelik/serbest metin ölçütleriyle sorgulanabilir ve
    kurum genel istatistikleri üretilebilir.
    """

    def __init__(self, db_yolu: "str | Path | None" = None) -> None:
        """
        Kayıt defterini başlatır; veritabanı ve tabloyu gerekirse oluşturur.

        Args:
            db_yolu: SQLite dosya yolu (None → data/processed/kayit_defteri.db).
                Testlerde geçici dizine yönlendirilebilir.
        """
        self.db_yolu = Path(db_yolu) if db_yolu else VARSAYILAN_DB_YOLU
        self.db_yolu.parent.mkdir(parents=True, exist_ok=True)
        baglanti = self._baglan()
        try:
            baglanti.execute(_TABLO_SQL)
            self._sema_gecisi(baglanti)
            baglanti.commit()
        finally:
            baglanti.close()
        logger.info(f"Kayıt defteri hazır: {self.db_yolu}")

    # ------------------------------------------------------------------
    # Bağlantı
    # ------------------------------------------------------------------

    def _baglan(self) -> sqlite3.Connection:
        """Kısa ömürlü SQLite bağlantısı açar (bkz. modül tasarım notu)."""
        baglanti = sqlite3.connect(str(self.db_yolu))
        baglanti.row_factory = sqlite3.Row
        return baglanti

    @staticmethod
    def _sema_gecisi(baglanti: sqlite3.Connection) -> None:
        """
        Eski şemalı defterleri yeni sütunlarla geriye uyumlu genişletir.

        PRAGMA table_info ile mevcut sütunlar okunur; _GECIS_SUTUNLARI
        içinden eksik olanlar ALTER TABLE ... ADD COLUMN ile eklenir.
        Eski kayıtlarda yeni sütunlar NULL kalır (emsal modülü bunu boş
        metin olarak tolere eder); mevcut veri hiçbir biçimde değişmez.
        """
        mevcut = {
            str(satir[1])
            for satir in baglanti.execute("PRAGMA table_info(islemler)")
        }
        for sutun, tip in _GECIS_SUTUNLARI.items():
            if sutun not in mevcut:
                # Sütun adı/tipi sabit modül sözlüğünden gelir; kullanıcı
                # girdisi değildir (CWE-89 riski yoktur).
                baglanti.execute(f"ALTER TABLE islemler ADD COLUMN {sutun} {tip}")
                logger.info(f"Kayıt defteri şeması genişletildi: {sutun} {tip}")

    # ------------------------------------------------------------------
    # Yazma
    # ------------------------------------------------------------------

    def kaydet(self, sonuc: dict, metin: str = "") -> int:
        """
        Pipeline sonucunu tek satırlık denetim kaydı olarak defterine işler.

        Eksik/bozuk alanlara toleranslıdır: bulunamayan alanlar boş/None
        yazılır; denetim izi hiçbir sonuç için atlanmaz.

        Args:
            sonuc: EndToEndPipeline.process/process_text çıktısı sözlük.
            metin: Evrakın ham metni (opsiyonel — sonuç sözlüğünde ham
                metin bulunmadığı için ayrı parametredir). İlk
                METIN_OZU_KARAKTER karakteri emsal arama belgesi olarak
                saklanır; boş bırakan mevcut çağrılar aynen çalışır.

        Returns:
            Eklenen kaydın otomatik artan kimlik (id) değeri.
        """
        sonuc = _guvenli_sozluk(sonuc)
        sinif = _guvenli_sozluk(sonuc.get("siniflandirma"))
        yonlendirme = _guvenli_sozluk(sonuc.get("yonlendirme"))
        oncelik_bilgisi = _guvenli_sozluk(sonuc.get("onceliklendirme"))
        format_denetimi = _guvenli_sozluk(sonuc.get("format_denetimi"))
        insan_onayi = _guvenli_sozluk(sonuc.get("insan_onayi"))
        eksikler = sonuc.get("eksik_bilgiler")
        eksik_sayisi = len(eksikler) if isinstance(eksikler, (list, tuple)) else 0

        son_tarih = (
            oncelik_bilgisi.get("son_tarih")
            or oncelik_bilgisi.get("son_islem_tarihi")
            or oncelik_bilgisi.get("termin_tarihi")
        )

        satir = (
            datetime.now().isoformat(timespec="seconds"),
            str(sonuc.get("input_file") or ""),
            str(sinif.get("tur") or ""),
            _guvenli_sayi(sinif.get("guven")),
            str(yonlendirme.get("birim") or ""),
            _guvenli_sayi(yonlendirme.get("guven")),
            str(oncelik_bilgisi.get("oncelik") or ""),
            str(son_tarih) if son_tarih else None,
            eksik_sayisi,
            1 if _kritik_eksik_var_mi(eksikler) else 0,
            _guvenli_sayi(format_denetimi.get("skor")),
            _guvenli_sayi(sonuc.get("islem_suresi_saniye")),
            1 if insan_onayi.get("gerekli") is True else 0,
            "; ".join(
                str(g) for g in (insan_onayi.get("gerekceler") or [])
            )[:1000],
            str(sonuc.get("ozet") or "").strip()[:200],
            str(metin or "").strip()[:METIN_OZU_KARAKTER],
            str(sonuc.get("yazi_turu") or ""),
        )

        baglanti = self._baglan()
        try:
            # GÜVENLİK: parametreli INSERT (CWE-89)
            imlec = baglanti.execute(
                """
                INSERT INTO islemler (
                    zaman, kaynak, tur, tur_guven, birim, birim_guven,
                    oncelik, son_tarih, eksik_sayisi, kritik_eksik,
                    format_skoru, sure_saniye, insan_onayi,
                    insan_onayi_gerekce, ozet_ilk_200,
                    metin_ozu, yazi_turu
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                satir,
            )
            baglanti.commit()
            kayit_no = int(imlec.lastrowid)
        finally:
            baglanti.close()

        logger.info(f"Kayıt defterine işlendi: no={kayit_no}, kaynak={satir[1]!r}")
        return kayit_no

    # ------------------------------------------------------------------
    # Sorgulama
    # ------------------------------------------------------------------

    def sorgula(
        self,
        tur: Optional[str] = None,
        birim: Optional[str] = None,
        oncelik: Optional[str] = None,
        metin_ara: Optional[str] = None,
        insan_onayi: Optional[bool] = None,
        limit: int = 50,
    ) -> "list[dict]":
        """
        Kayıtları ölçütlere göre listeler (en yeni kayıt en üstte).

        Args:
            tur: Evrak türü kodu tam eşleşmesi (örn. 'dilekce').
            birim: Yönlendirilen birim adı tam eşleşmesi.
            oncelik: Öncelik düzeyi tam eşleşmesi (örn. 'ivedi').
            metin_ara: Özet ve kaynak alanlarında geçen serbest metin
                (düz metin olarak aranır; joker karakterler etkisizdir).
            insan_onayi: True → yalnızca insan onayı bekleyen kayıtlar
                (İnsan Onayı Kuyruğu); False → onay gerektirmeyenler.
            limit: Döndürülecek azami kayıt sayısı (1..500 aralığına kırpılır).

        Returns:
            Sütun adlarıyla anahtarlanmış kayıt sözlükleri listesi.
        """
        # GÜVENLİK: tüm ölçütler parametre olarak bağlanır; SQL metnine
        # hiçbir kullanıcı girdisi eklenmez (CWE-89).
        kosullar: "list[str]" = []
        parametreler: "list[Any]" = []
        if tur:
            kosullar.append("tur = ?")
            parametreler.append(str(tur))
        if birim:
            kosullar.append("birim = ?")
            parametreler.append(str(birim))
        if oncelik:
            kosullar.append("oncelik = ?")
            parametreler.append(str(oncelik))
        if insan_onayi is not None:
            kosullar.append("insan_onayi = ?")
            parametreler.append(1 if insan_onayi else 0)
        if metin_ara:
            kosullar.append(
                "(ozet_ilk_200 LIKE ? ESCAPE '\\' OR kaynak LIKE ? ESCAPE '\\')"
            )
            desen = _like_deseni(str(metin_ara))
            parametreler.extend([desen, desen])

        sql = "SELECT * FROM islemler"
        if kosullar:
            sql += " WHERE " + " AND ".join(kosullar)
        sql += " ORDER BY id DESC LIMIT ?"

        try:
            guvenli_limit = int(limit)
        except (TypeError, ValueError):
            guvenli_limit = 50
        parametreler.append(max(1, min(_AZAMI_LIMIT, guvenli_limit)))

        baglanti = self._baglan()
        try:
            satirlar = baglanti.execute(sql, parametreler).fetchall()
        finally:
            baglanti.close()
        return [dict(satir) for satir in satirlar]

    def tum_kayitlar_emsal_icin(self) -> "list[dict]":
        """
        Emsal (benzer geçmiş evrak) araması için tüm kayıtların özünü verir.

        Emsal dizini defterin TAMAMI üzerinde kurulduğu için sorgula()'daki
        sayfa limiti uygulanmaz; buna karşılık yalnızca emsal modülünün
        gereksindiği alanlar seçilir (tam satır dönmez). Şema geçişinden
        önce yazılmış eski kayıtlarda metin_ozu/yazi_turu NULL olabilir;
        bunlar boş metne indirgenir ki tüketici tarafında tür denetimi
        gerekmesin.

        Returns:
            [{id, kaynak, tur, birim, zaman, ozet_ilk_200, metin_ozu,
              yazi_turu}, ...] — id artan sırada (eskiden yeniye).
        """
        baglanti = self._baglan()
        try:
            satirlar = baglanti.execute(
                """
                SELECT id, kaynak, tur, birim, zaman, ozet_ilk_200,
                       COALESCE(metin_ozu, '') AS metin_ozu,
                       COALESCE(yazi_turu, '') AS yazi_turu
                FROM islemler
                ORDER BY id
                """
            ).fetchall()
        finally:
            baglanti.close()
        return [dict(satir) for satir in satirlar]

    def istatistik(self) -> dict:
        """
        Defter genel istatistiklerini üretir.

        Returns:
            {
                "toplam": int,
                "tur_dagilimi": {tur_kodu: adet},
                "birim_dagilimi": {birim: adet},
                "oncelik_dagilimi": {oncelik: adet},
                "ort_sure_saniye": float,
                "insan_onayi_sayisi": int,
                "kritik_eksikli_sayisi": int,
            }
        """
        baglanti = self._baglan()
        try:
            toplam, ort_sure, insan_onayi, kritik = baglanti.execute(
                """
                SELECT COUNT(*),
                       AVG(sure_saniye),
                       COALESCE(SUM(insan_onayi), 0),
                       COALESCE(SUM(kritik_eksik), 0)
                FROM islemler
                """
            ).fetchone()

            def _dagilim(sutun: str) -> dict:
                # Sütun adı sabit çağrı listesinden gelir (kullanıcı girdisi
                # değildir); değerler yine parametresiz gruplanabilir.
                satirlar = baglanti.execute(
                    f"SELECT {sutun}, COUNT(*) AS adet FROM islemler "
                    f"WHERE {sutun} != '' GROUP BY {sutun} ORDER BY adet DESC"
                ).fetchall()
                return {str(s[0]): int(s[1]) for s in satirlar}

            tur_dagilimi = _dagilim("tur")
            birim_dagilimi = _dagilim("birim")
            oncelik_dagilimi = _dagilim("oncelik")
        finally:
            baglanti.close()

        return {
            "toplam": int(toplam or 0),
            "tur_dagilimi": tur_dagilimi,
            "birim_dagilimi": birim_dagilimi,
            "oncelik_dagilimi": oncelik_dagilimi,
            "ort_sure_saniye": round(float(ort_sure), 3) if ort_sure is not None else 0.0,
            "insan_onayi_sayisi": int(insan_onayi or 0),
            "kritik_eksikli_sayisi": int(kritik or 0),
        }
