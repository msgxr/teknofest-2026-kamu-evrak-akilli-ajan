"""
LLM Wrapper — Büyük Dil Modeli entegrasyon katmanı.

Farklı LLM sağlayıcılarını (OpenAI, HuggingFace, yerel modeller)
tek bir arayüz üzerinden kullanmaya olanak tanır.
"""

import logging
from typing import Optional

logger = logging.getLogger("kamu_evrak_ajan.llm")


class LLMWrapper:
    """
    LLM Wrapper sınıfı.

    Farklı LLM backend'lerini destekler:
    - OpenAI API (GPT-4o, GPT-4o-mini)
    - HuggingFace Transformers (yerel model)
    - Ollama (yerel çalıştırma)
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        """
        LLM Wrapper'ı başlatır.

        Args:
            model_name: Model adı (None ise config'den alınır)
            temperature: Sıcaklık parametresi
            max_tokens: Maksimum token sayısı
        """
        from src.config import settings

        self.model_name = model_name or settings.llm.model_name
        self.temperature = temperature or settings.llm.temperature
        self.max_tokens = max_tokens or settings.llm.max_tokens
        self._client = None

        logger.info(f"LLM Wrapper başlatıldı: {self.model_name}")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Verilen prompt için metin üretir.

        Args:
            prompt: Kullanıcı prompt'u
            system_prompt: Sistem prompt'u (opsiyonel)

        Returns:
            Üretilen metin
        """
        if "gpt" in self.model_name.lower() or "openai" in self.model_name.lower():
            return self._generate_openai(prompt, system_prompt)
        else:
            return self._generate_transformers(prompt, system_prompt)

    def _generate_openai(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """OpenAI API ile metin üretir."""
        try:
            from openai import OpenAI
            from src.config import settings

            if self._client is None:
                self._client = OpenAI(api_key=settings.llm.openai_api_key)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            return response.choices[0].message.content.strip()

        except ImportError:
            raise RuntimeError("openai kütüphanesi yüklü değil: pip install openai")
        except Exception as e:
            logger.error(f"OpenAI API hatası: {e}")
            raise

    def _generate_transformers(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """HuggingFace Transformers ile metin üretir."""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

            if self._client is None:
                logger.info(f"Model yükleniyor: {self.model_name}")
                self._client = pipeline(
                    "text-generation",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    max_new_tokens=self.max_tokens,
                    temperature=self.temperature,
                    do_sample=True,
                )

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            result = self._client(full_prompt)
            generated = result[0]["generated_text"]

            # Prompt'u çıktıdan çıkar
            if generated.startswith(full_prompt):
                generated = generated[len(full_prompt):].strip()

            return generated

        except ImportError:
            raise RuntimeError(
                "transformers kütüphanesi yüklü değil: pip install transformers torch"
            )
        except Exception as e:
            logger.error(f"Transformers hatası: {e}")
            raise
