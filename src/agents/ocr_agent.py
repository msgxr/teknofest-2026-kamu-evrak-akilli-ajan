"""
OCR Agent — Evrak okuma ve metin çıkarımı.

PDF, görüntü (PNG, JPG, TIFF) ve metin dosyalarından
metin çıkarımı yapan agent. Tesseract ve EasyOCR destekler.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.ocr")


class OCRAgent:
    """
    OCR Agent — Evrak okuma ve metin çıkarımı.

    Desteklenen formatlar:
        - PDF dosyaları
        - Görüntü dosyaları (PNG, JPG, JPEG, TIFF, BMP)
        - Metin dosyaları (TXT, MD)

    Şartname Referansı (Görev 1):
        "Evrakı OCR veya doğrudan metin olarak okuyabilme"
    """

    SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
    SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
    SUPPORTED_PDF_EXTENSIONS = {".pdf"}

    def __init__(self, engine: str = "tesseract") -> None:
        """
        OCR Agent'ı başlatır.

        Args:
            engine: OCR motoru ('tesseract' veya 'easyocr')
        """
        self.engine = engine
        logger.info(f"OCR Agent başlatıldı (motor: {engine})")

    def run(self, state: "AgentState") -> "AgentState":
        """
        Evrak dosyasından metin çıkarır.

        Args:
            state: Mevcut agent durumu

        Returns:
            Güncellenen agent durumu
        """
        file_path = Path(state.input_file)

        if not file_path.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

        ext = file_path.suffix.lower()

        if ext in self.SUPPORTED_TEXT_EXTENSIONS:
            text = self._read_text_file(file_path)
        elif ext in self.SUPPORTED_PDF_EXTENSIONS:
            text = self._read_pdf(file_path)
        elif ext in self.SUPPORTED_IMAGE_EXTENSIONS:
            text = self._read_image(file_path)
        else:
            raise ValueError(f"Desteklenmeyen dosya formatı: {ext}")

        state.raw_text = text
        state.ocr_result = {
            "source_file": str(file_path),
            "file_type": ext,
            "character_count": len(text),
            "word_count": len(text.split()),
            "engine_used": self.engine if ext in self.SUPPORTED_IMAGE_EXTENSIONS else "direct",
        }

        logger.info(
            f"Metin çıkarıldı: {state.ocr_result['word_count']} kelime, "
            f"{state.ocr_result['character_count']} karakter"
        )

        return state

    def _read_text_file(self, file_path: Path) -> str:
        """Metin dosyasını doğrudan okur."""
        logger.debug(f"Metin dosyası okunuyor: {file_path}")
        return file_path.read_text(encoding="utf-8")

    def _read_pdf(self, file_path: Path) -> str:
        """PDF dosyasından metin çıkarır."""
        logger.debug(f"PDF dosyası okunuyor: {file_path}")
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            text_parts = []
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                    logger.debug(f"Sayfa {page_num}: {len(page_text)} karakter")

            full_text = "\n\n".join(text_parts)

            # Eğer PDF'ten metin çıkarılamazsa OCR dene
            if not full_text.strip():
                logger.info("PDF'ten metin çıkarılamadı, OCR deneniyor...")
                full_text = self._ocr_pdf(file_path)

            return full_text

        except ImportError:
            logger.warning("PyPDF2 yüklü değil, OCR ile deneniyor...")
            return self._ocr_pdf(file_path)

    def _ocr_pdf(self, file_path: Path) -> str:
        """PDF dosyasını görüntüye çevirip OCR uygular."""
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(str(file_path))
            text_parts = []

            for i, image in enumerate(images, 1):
                page_text = self._ocr_image(image)
                text_parts.append(page_text)
                logger.debug(f"OCR Sayfa {i}: {len(page_text)} karakter")

            return "\n\n".join(text_parts)

        except ImportError:
            raise RuntimeError("pdf2image kütüphanesi yüklü değil: pip install pdf2image")

    def _read_image(self, file_path: Path) -> str:
        """Görüntü dosyasından OCR ile metin çıkarır."""
        logger.debug(f"Görüntü dosyası okunuyor: {file_path}")
        from PIL import Image

        image = Image.open(file_path)
        return self._ocr_image(image)

    def _ocr_image(self, image) -> str:
        """
        Bir görüntüye OCR uygular.

        Args:
            image: PIL Image nesnesi

        Returns:
            Çıkarılan metin
        """
        if self.engine == "tesseract":
            return self._tesseract_ocr(image)
        elif self.engine == "easyocr":
            return self._easyocr_ocr(image)
        else:
            raise ValueError(f"Desteklenmeyen OCR motoru: {self.engine}")

    def _tesseract_ocr(self, image) -> str:
        """Tesseract OCR ile metin çıkarır."""
        try:
            import pytesseract
            from src.config import settings

            pytesseract.pytesseract.tesseract_cmd = settings.ocr.tesseract_cmd
            text = pytesseract.image_to_string(image, lang=settings.ocr.tesseract_lang)
            return text.strip()

        except ImportError:
            raise RuntimeError("pytesseract yüklü değil: pip install pytesseract")

    def _easyocr_ocr(self, image) -> str:
        """EasyOCR ile metin çıkarır."""
        try:
            import easyocr
            import numpy as np

            reader = easyocr.Reader(["tr"], gpu=False)
            image_array = np.array(image)
            results = reader.readtext(image_array, detail=0)
            return "\n".join(results)

        except ImportError:
            raise RuntimeError("easyocr yüklü değil: pip install easyocr")
