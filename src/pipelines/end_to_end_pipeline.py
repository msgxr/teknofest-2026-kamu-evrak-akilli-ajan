"""
Uçtan Uca Pipeline — Tüm görevleri birleştiren ana iş akışı.

Görev 1 (Evrak Sınıflandırma ve İçerik Analizi) ve
Görev 2 (Resmi Yazı Taslaklama ve Birim Yönlendirme)
görevlerini bütüncül olarak çalıştırır.

Şartname Referansı:
    "Değerlendirme, iki görevin bütüncül olarak yerine getirildiği
     uçtan uca senaryolar üzerinden yapılacaktır."
"""

import logging
import time
from typing import Optional

from src.agents.orchestrator import OrchestratorAgent

logger = logging.getLogger("kamu_evrak_ajan.pipeline")


class EndToEndPipeline:
    """
    Uçtan uca evrak işleme pipeline'ı.

    Evrak girişinden yazı taslağı ve birim yönlendirmesine kadar
    tüm süreci yönetir. İsteğe bağlı olarak her işlemi evrak kayıt
    defterine (SQLite denetim izi) işler; kayıt VARSAYILAN OLARAK
    KAPALIDIR ki değerlendirme/toplu ölçüm betikleri yan etki üretmesin —
    yalnızca arayüz/CLI gibi gerçek kullanım akışları açar.
    """

    def __init__(
        self,
        kayit_defteri_aktif: bool = False,
        kayit_defteri_yolu: Optional[str] = None,
    ) -> None:
        """
        Pipeline'ı başlatır.

        Args:
            kayit_defteri_aktif: True ise her işlem sonucu evrak kayıt
                defterine (SQLite) işlenir. Varsayılan False — mevcut
                çağrılar ve değerlendirme betikleri etkilenmez.
            kayit_defteri_yolu: Kayıt defteri veritabanı dosya yolu
                (None → varsayılan: data/processed/kayit_defteri.db).
        """
        self.orchestrator = OrchestratorAgent()
        self.kayit_defteri = None
        if kayit_defteri_aktif:
            try:
                from src.utils.kayit_defteri import KayitDefteri

                self.kayit_defteri = KayitDefteri(kayit_defteri_yolu)
            except Exception as exc:
                # Denetim izi açılamazsa evrak işleme durmamalı; kayıt
                # kapalı sürdürülür ve durum loglanır.
                logger.warning(f"Kayıt defteri başlatılamadı; kayıt kapalı: {exc}")
        logger.info(
            "Uçtan uca pipeline başlatıldı"
            f" (kayıt defteri: {'aktif' if self.kayit_defteri else 'kapalı'})."
        )

    def process(self, input_file: str, mode: str = "full", kayit: bool = True) -> dict:
        """
        Evrak dosyasını uçtan uca işler.

        Args:
            input_file: İşlenecek evrak dosya yolu
            mode: Çalışma modu ('full', 'classify', 'draft')
            kayit: False ise bu işlem kayıt defterine işlenmez (defter
                aktif olsa bile). Defter zaten kapalıysa etkisizdir.

        Returns:
            Tüm işlem sonuçlarını içeren sözlük
        """
        start_time = time.time()
        logger.info(f"Pipeline başlatıldı: {input_file}")

        # Orkestratör ile tüm agent'ları çalıştır
        results = self.orchestrator.process(input_file, mode=mode)

        # İşlem süresini ekle
        elapsed = time.time() - start_time
        results["islem_suresi_saniye"] = round(elapsed, 2)

        logger.info(f"Pipeline tamamlandı: {elapsed:.2f} saniye")
        self._kayda_gecir(results, kayit)
        return results

    def process_text(
        self,
        text: str,
        mode: str = "full",
        source_name: str = "dogrudan_metin",
        kayit: bool = True,
    ) -> dict:
        """
        Doğrudan metin girişini uçtan uca işler (dosya/OCR adımı olmadan).

        Args:
            text: İşlenecek evrak metni
            mode: Çalışma modu ('full', 'classify', 'draft')
            source_name: Kaynak etiketi (raporlama/kayıt defterinde görünür)
            kayit: False ise bu işlem kayıt defterine işlenmez

        Returns:
            Tüm işlem sonuçlarını içeren sözlük
        """
        start_time = time.time()
        results = self.orchestrator.process_text(text, mode=mode, source_name=source_name)
        results["islem_suresi_saniye"] = round(time.time() - start_time, 2)
        self._kayda_gecir(results, kayit)
        return results

    def process_batch(
        self, input_files: list[str], mode: str = "full", kayit: bool = True
    ) -> list[dict]:
        """
        Birden fazla evrak dosyasını sırayla işler.

        Args:
            input_files: İşlenecek evrak dosya yolları listesi
            mode: Çalışma modu
            kayit: False ise işlemler kayıt defterine işlenmez

        Returns:
            Her dosya için sonuçları içeren liste
        """
        results = []
        for i, file_path in enumerate(input_files, 1):
            logger.info(f"Toplu işlem {i}/{len(input_files)}: {file_path}")
            result = self.process(file_path, mode=mode, kayit=kayit)
            results.append(result)
        return results

    def _kayda_gecir(self, results: dict, kayit: bool) -> None:
        """
        İşlem sonucunu evrak kayıt defterine işler (defter aktifse).

        Kayıt yazımı hiçbir koşulda evrak işleme sonucunu düşürmez:
        denetim izi hatası loglanır ve sonuç aynen döndürülür.
        """
        if not kayit or self.kayit_defteri is None:
            return
        try:
            # Emsal arama (kurumsal hafıza) için evrak metninin özü de kaydedilir
            evrak_metni = ""
            try:
                evrak_metni = self.orchestrator.state.raw_text or ""
            except Exception:
                pass
            kayit_no = self.kayit_defteri.kaydet(results, metin=evrak_metni)
            logger.info(f"İşlem kayıt defterine işlendi (kayıt no: {kayit_no}).")
        except Exception as exc:
            logger.warning(f"Kayıt defterine yazılamadı (sonuç etkilenmez): {exc}")
