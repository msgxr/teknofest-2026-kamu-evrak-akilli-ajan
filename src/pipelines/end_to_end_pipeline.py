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
    tüm süreci yönetir.
    """

    def __init__(self) -> None:
        """Pipeline'ı başlatır."""
        self.orchestrator = OrchestratorAgent()
        logger.info("Uçtan uca pipeline başlatıldı.")

    def process(self, input_file: str, mode: str = "full") -> dict:
        """
        Evrak dosyasını uçtan uca işler.

        Args:
            input_file: İşlenecek evrak dosya yolu
            mode: Çalışma modu ('full', 'classify', 'draft')

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
        return results

    def process_batch(self, input_files: list[str], mode: str = "full") -> list[dict]:
        """
        Birden fazla evrak dosyasını sırayla işler.

        Args:
            input_files: İşlenecek evrak dosya yolları listesi
            mode: Çalışma modu

        Returns:
            Her dosya için sonuçları içeren liste
        """
        results = []
        for i, file_path in enumerate(input_files, 1):
            logger.info(f"Toplu işlem {i}/{len(input_files)}: {file_path}")
            result = self.process(file_path, mode=mode)
            results.append(result)
        return results
