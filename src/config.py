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

    # Backend seçimi: '' (otomatik), 'openai', 'ollama', 'offline'
    backend: str = ""

    # OpenAI-uyumlu API ayarları (OpenAI, OpenRouter, Groq, vLLM, LM Studio...)
    model_name: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Ollama (yerel) ayarları
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Üretim parametreleri
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout_seconds: int = 90
    hf_token: Optional[str] = None

    class Config:
        env_prefix = "LLM_"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Geriye dönük uyumluluk: OPENAI_API_KEY doğrudan da okunabilsin
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY") or None


class OCRSettings(BaseSettings):
    """OCR motor ayarları."""

    # Alan adları TESSERACT_CMD / TESSERACT_LANG ortam değişkenleriyle eşleşir
    tesseract_cmd: str = "tesseract"
    tesseract_lang: str = "tur"


class EmbeddingSettings(BaseSettings):
    """Embedding ve hibrit mevzuat RAG (opsiyonel semantik katman) ayarları."""

    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Hibrit mevzuat RAG'in opsiyonel yoğun (dense) arama katmanı.
    # Bilinçli olarak varsayılan KAPALI: ilk kullanımda model indirme
    # gerektirdiğinden kapalı ağda sürpriz ağ trafiği oluşturmamalıdır
    # (offline-first ilkesi). EMBEDDING_SEMANTIK_AKTIF=1 ile açılır.
    semantik_aktif: bool = False
    semantik_model: str = "ytu-ce-cosmos/turkish-e5-large"

    # Opsiyonel yeniden sıralama (rerank) katmanı; EMBEDDING_RERANK_AKTIF=1
    rerank_aktif: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

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
