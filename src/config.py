"""
Uygulama konfigürasyon yönetimi.

Ortam değişkenlerini yükler ve uygulama genelinde kullanılan ayarları tanımlar.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent


class LLMSettings(BaseSettings):
    """LLM model ayarları."""

    model_name: str = "meta-llama/Llama-3.1-8B-Instruct"
    temperature: float = 0.1
    max_tokens: int = 4096
    openai_api_key: Optional[str] = None
    hf_token: Optional[str] = None

    class Config:
        env_prefix = "LLM_"


class OCRSettings(BaseSettings):
    """OCR motor ayarları."""

    tesseract_cmd: str = "tesseract"
    tesseract_lang: str = "tur"

    class Config:
        env_prefix = "TESSERACT_"


class EmbeddingSettings(BaseSettings):
    """Embedding model ayarları."""

    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    class Config:
        env_prefix = "EMBEDDING_"


class ChromaSettings(BaseSettings):
    """ChromaDB vektör veritabanı ayarları."""

    persist_dir: str = str(PROJECT_ROOT / "data" / "chroma_db")
    collection_name: str = "mevzuat"

    class Config:
        env_prefix = "CHROMA_"


class AppSettings(BaseSettings):
    """Genel uygulama ayarları."""

    host: str = "localhost"
    port: int = 8501
    log_level: str = "INFO"
    debug: bool = False

    # Veri dizinleri
    data_raw_dir: str = str(PROJECT_ROOT / "data" / "raw")
    data_processed_dir: str = str(PROJECT_ROOT / "data" / "processed")
    templates_dir: str = str(PROJECT_ROOT / "src" / "templates")
    mevzuat_dir: str = str(PROJECT_ROOT / "data" / "raw" / "mevzuat_metinleri")

    class Config:
        env_prefix = "APP_"


class Settings:
    """Tüm ayarları tek bir yerde toplayan ana konfigürasyon sınıfı."""

    def __init__(self) -> None:
        self.llm = LLMSettings()
        self.ocr = OCRSettings()
        self.embedding = EmbeddingSettings()
        self.chroma = ChromaSettings()
        self.app = AppSettings()

    def __repr__(self) -> str:
        return (
            f"Settings(\n"
            f"  llm_model={self.llm.model_name},\n"
            f"  ocr_lang={self.ocr.tesseract_lang},\n"
            f"  embedding_model={self.embedding.model_name},\n"
            f"  debug={self.app.debug}\n"
            f")"
        )


# Global ayarlar nesnesi
settings = Settings()
