"""
Bilgi Çıkarım Agent — Evraktan anahtar bilgileri çıkarma.

Şartname Referansı (Görev 1):
    "İçerikte geçen önemli bilgi unsurlarını çıkarma"
"""

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.info_extraction")


class InfoExtractionAgent:
    """
    Bilgi çıkarım agent'ı.

    Evrak metninden anahtar bilgileri (tarih, kurum, konu, muhatap,
    referans numarası vb.) çıkarır.
    """

    def __init__(self) -> None:
        logger.info("Bilgi Çıkarım Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evraktan anahtar bilgileri çıkarır."""
        text = state.raw_text

        extracted = {
            "tarihler": self._extract_dates(text),
            "kurum_adlari": self._extract_organizations(text),
            "kisi_adlari": self._extract_person_names(text),
            "referans_numaralari": self._extract_reference_numbers(text),
            "konu": self._extract_subject(text),
            "muhatap": self._extract_recipient(text),
        }

        state.extracted_info = extracted
        logger.info(f"Bilgi çıkarıldı: {sum(len(v) if isinstance(v, list) else (1 if v else 0) for v in extracted.values())} unsur")
        return state

    def _extract_dates(self, text: str) -> list[str]:
        """Metinden tarih bilgilerini çıkarır."""
        patterns = [
            r"\d{2}[./]\d{2}[./]\d{4}",
            r"\d{2}\s+(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}",
            r"\d{4}[/-]\d{2}[/-]\d{2}",
        ]
        dates = []
        for pattern in patterns:
            dates.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(dates))

    def _extract_organizations(self, text: str) -> list[str]:
        """Metinden kurum/birim adlarını çıkarır."""
        patterns = [
            r"(?:T\.C\.\s+)?[\w\s]+(?:Bakanlığı|Müdürlüğü|Başkanlığı|Dairesi|Kurumu|Enstitüsü)",
            r"[\w\s]+(?:Valiliği|Kaymakamlığı|Belediyesi|Üniversitesi)",
        ]
        orgs = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            orgs.extend([m.strip() for m in matches])
        return list(set(orgs))[:10]

    def _extract_person_names(self, text: str) -> list[str]:
        """Metinden kişi adlarını çıkarır (LLM ile geliştirilecek)."""
        # TODO: NER modeli ile geliştirilecek
        return []

    def _extract_reference_numbers(self, text: str) -> list[str]:
        """Metinden sayı/referans numaralarını çıkarır."""
        patterns = [
            r"Say[ıi]\s*:\s*([\w\d\-/]+)",
            r"No\s*:\s*([\w\d\-/]+)",
            r"E-\d+",
        ]
        refs = []
        for pattern in patterns:
            refs.extend(re.findall(pattern, text))
        return list(set(refs))

    def _extract_subject(self, text: str) -> str:
        """Metinden konu bilgisini çıkarır."""
        match = re.search(r"Konu\s*:\s*(.+?)(?:\n|$)", text)
        return match.group(1).strip() if match else ""

    def _extract_recipient(self, text: str) -> str:
        """Metinden muhatap bilgisini çıkarır."""
        patterns = [
            r"(?:Sayın|İlgi(?:li)?)\s+(.+?)(?:\n|$)",
            r"(.+?)\s+(?:MAKAMINA|makamına)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ""
