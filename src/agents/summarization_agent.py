"""
Özet Oluşturma Agent — Evrak özeti oluşturma.

Şartname Referansı (Görev 1):
    "Evraka ilişkin kısa ve öz bir özet oluşturabilme"
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.summarization")


class SummarizationAgent:
    """
    Özet oluşturma agent'ı.

    Evrak metninden kısa ve öz bir özet üretir.
    LLM kullanarak Türkçe özet oluşturur.
    """

    def __init__(self) -> None:
        logger.info("Özet Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evrak metninden özet oluşturur."""
        text = state.raw_text
        evrak_turu = state.classification.get("tur_adi", "Bilinmiyor")
        extracted = state.extracted_info

        if not text.strip():
            state.summary = "Metin çıkarılamadığı için özet oluşturulamadı."
            return state

        summary = self._generate_summary(text, evrak_turu, extracted)
        state.summary = summary
        logger.info(f"Özet oluşturuldu: {len(summary)} karakter")
        return state

    def _generate_summary(self, text: str, evrak_turu: str, extracted: dict) -> str:
        """
        LLM kullanarak özet oluşturur.

        Args:
            text: Evrak metni
            evrak_turu: Belirlenen evrak türü
            extracted: Çıkarılan bilgiler

        Returns:
            Oluşturulan özet metni
        """
        try:
            from src.models.llm_wrapper import LLMWrapper

            llm = LLMWrapper()

            prompt = f"""Aşağıdaki resmi evrak metninin kısa ve öz bir özetini Türkçe olarak oluştur.

Evrak Türü: {evrak_turu}
Konu: {extracted.get('konu', 'Belirtilmemiş')}

Evrak Metni:
---
{text[:4000]}
---

Kurallar:
- Özet en fazla 3-4 cümle olsun
- Resmi ve nesnel bir dil kullan
- Evrakın ana amacını, talebini veya kararını vurgula
- Tarih ve referans bilgilerini dahil et
"""
            return llm.generate(prompt)

        except Exception as e:
            logger.warning(f"LLM özet oluşturulamadı, extractive yöntem kullanılıyor: {e}")
            return self._extractive_summary(text)

    def _extractive_summary(self, text: str) -> str:
        """
        Extractive yöntemle özet oluşturur (LLM kullanılamadığında).

        Metnin ilk paragraflarından önemli cümleleri seçer.
        """
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 20]

        if not sentences:
            return "Metin çok kısa olduğu için özet oluşturulamadı."

        # İlk 3-4 anlamlı cümleyi al
        summary_sentences = sentences[:min(4, len(sentences))]
        return ". ".join(summary_sentences) + "."
