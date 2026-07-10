"""
Sınıflandırma Agent — Evrak türü belirleme.

Evrak metnini analiz ederek türünü (dilekçe, üst yazı, cevap yazısı,
tutanak, rapor vb.) belirleyen agent.

Şartname Referansı (Görev 1):
    "Metni anlamlandırarak evrakın türünü belirleme"
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.classification")

# Desteklenen evrak türleri
EVRAK_TURLERI = {
    "dilekce": {
        "ad": "Dilekçe",
        "aciklama": "Vatandaş veya kurumlardan gelen talep/şikayet belgesi",
        "anahtar_kelimeler": ["dilekçe", "talep", "başvuru", "rica ederim", "arz ederim"],
    },
    "ust_yazi": {
        "ad": "Üst Yazı",
        "aciklama": "Bir evrakın üst makama sunulması için hazırlanan yazı",
        "anahtar_kelimeler": ["üst yazı", "ilgi", "ekte sunulmuştur", "makamınıza"],
    },
    "cevap_yazisi": {
        "ad": "Cevap Yazısı",
        "aciklama": "Gelen bir evrak veya yazıya yanıt olarak hazırlanan resmi yazı",
        "anahtar_kelimeler": ["ilgide kayıtlı", "cevaben", "yanıt olarak", "karşılık"],
    },
    "bilgilendirme": {
        "ad": "Bilgilendirme Yazısı",
        "aciklama": "Bilgi aktarımı veya duyuru amaçlı yazı",
        "anahtar_kelimeler": ["bilgi", "bilgilerinize", "duyuru", "bilgilendirme"],
    },
    "tutanak": {
        "ad": "Tutanak",
        "aciklama": "Toplantı veya inceleme sonuçlarını belgeleyen yazı",
        "anahtar_kelimeler": ["tutanak", "toplantı", "katılımcılar", "gündem"],
    },
    "rapor": {
        "ad": "Rapor",
        "aciklama": "İnceleme, araştırma veya değerlendirme sonuçlarını içeren belge",
        "anahtar_kelimeler": ["rapor", "inceleme", "değerlendirme", "sonuç", "bulgular"],
    },
    "genelge": {
        "ad": "Genelge",
        "aciklama": "Tüm birimlere yönelik genel talimat veya bilgilendirme",
        "anahtar_kelimeler": ["genelge", "tüm birimlere", "genel talimat"],
    },
    "onayli_belge": {
        "ad": "Onaylı Belge",
        "aciklama": "Resmi onay veya tasdik içeren belge",
        "anahtar_kelimeler": ["onay", "tasdik", "uygun görülmüştür", "onaylanmıştır"],
    },
    "diger": {
        "ad": "Diğer",
        "aciklama": "Yukarıdaki kategorilere girmeyen evrak",
        "anahtar_kelimeler": [],
    },
}


class ClassificationAgent:
    """
    Evrak sınıflandırma agent'ı.

    Gelen evrakın türünü belirler. İki yöntem kullanılabilir:
    1. Kural tabanlı (anahtar kelime eşleştirme) — hızlı, basit
    2. LLM tabanlı (prompt ile sınıflandırma) — daha doğru, yavaş
    """

    def __init__(self, method: str = "llm") -> None:
        """
        Sınıflandırma agent'ını başlatır.

        Args:
            method: Sınıflandırma yöntemi ('rule_based' veya 'llm')
        """
        self.method = method
        logger.info(f"Sınıflandırma Agent başlatıldı (yöntem: {method})")

    def run(self, state: "AgentState") -> "AgentState":
        """
        Evrak metnini sınıflandırır.

        Args:
            state: Mevcut agent durumu

        Returns:
            Güncellenen agent durumu
        """
        text = state.raw_text

        if not text.strip():
            state.classification = {
                "tur": "bilinmiyor",
                "tur_adi": "Bilinmiyor",
                "guven": 0.0,
                "aciklama": "Metin çıkarılamadı",
            }
            return state

        if self.method == "rule_based":
            result = self._classify_rule_based(text)
        else:
            result = self._classify_with_llm(text)

        state.classification = result
        logger.info(f"Sınıflandırma sonucu: {result['tur_adi']} (güven: {result['guven']:.2f})")
        return state

    def _classify_rule_based(self, text: str) -> dict:
        """
        Kural tabanlı sınıflandırma — anahtar kelime eşleştirmesi.

        Args:
            text: Evrak metni

        Returns:
            Sınıflandırma sonucu
        """
        text_lower = text.lower()
        scores: dict[str, int] = {}

        for tur_key, tur_info in EVRAK_TURLERI.items():
            score = 0
            for keyword in tur_info["anahtar_kelimeler"]:
                if keyword.lower() in text_lower:
                    score += 1
            scores[tur_key] = score

        if not scores or max(scores.values()) == 0:
            best_type = "diger"
            confidence = 0.1
        else:
            best_type = max(scores, key=scores.get)
            total_keywords = len(EVRAK_TURLERI[best_type]["anahtar_kelimeler"])
            confidence = scores[best_type] / max(total_keywords, 1)

        tur_info = EVRAK_TURLERI[best_type]
        return {
            "tur": best_type,
            "tur_adi": tur_info["ad"],
            "guven": min(confidence, 1.0),
            "aciklama": tur_info["aciklama"],
            "tum_skorlar": scores,
        }

    def _classify_with_llm(self, text: str) -> dict:
        """
        LLM tabanlı sınıflandırma.

        Args:
            text: Evrak metni

        Returns:
            Sınıflandırma sonucu
        """
        from src.models.llm_wrapper import LLMWrapper

        llm = LLMWrapper()

        turler_listesi = "\n".join(
            f"- {key}: {info['ad']} — {info['aciklama']}"
            for key, info in EVRAK_TURLERI.items()
        )

        prompt = f"""Aşağıdaki evrak metnini analiz et ve evrak türünü belirle.

Desteklenen evrak türleri:
{turler_listesi}

Evrak Metni:
---
{text[:3000]}
---

Yanıtını aşağıdaki formatta ver:
TÜR: <evrak_turu_key>
GÜVEN: <0.0 ile 1.0 arası güven skoru>
GEREKÇE: <sınıflandırma gerekçesi>
"""

        response = llm.generate(prompt)
        return self._parse_llm_response(response)

    def _parse_llm_response(self, response: str) -> dict:
        """LLM yanıtını ayrıştırır."""
        lines = response.strip().split("\n")
        result = {
            "tur": "diger",
            "tur_adi": "Diğer",
            "guven": 0.5,
            "aciklama": "",
        }

        for line in lines:
            if line.startswith("TÜR:"):
                tur_key = line.split(":", 1)[1].strip().lower()
                if tur_key in EVRAK_TURLERI:
                    result["tur"] = tur_key
                    result["tur_adi"] = EVRAK_TURLERI[tur_key]["ad"]
                    result["aciklama"] = EVRAK_TURLERI[tur_key]["aciklama"]
            elif line.startswith("GÜVEN:"):
                try:
                    result["guven"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("GEREKÇE:"):
                result["gerekce"] = line.split(":", 1)[1].strip()

        return result
