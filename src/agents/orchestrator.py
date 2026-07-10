"""
Orkestratör Agent — Tüm agent'ları koordine eden ana yönetici.

Bu agent, evrak işleme sürecindeki tüm alt agent'ları yönetir,
görev sırasını belirler ve sonuçları birleştirir. LangGraph tabanlı
state machine ile iş akışını kontrol eder.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("kamu_evrak_ajan.orchestrator")


@dataclass
class AgentState:
    """
    Agent'lar arası paylaşılan durum nesnesi.

    Evrak işleme sürecinin her aşamasında güncellenir ve
    bir sonraki agent'a aktarılır.
    """

    # Giriş
    input_file: str = ""
    raw_text: str = ""

    # Görev 1 sonuçları
    ocr_result: dict = field(default_factory=dict)
    classification: dict = field(default_factory=dict)
    extracted_info: dict = field(default_factory=dict)
    missing_info: list = field(default_factory=list)
    legislation_matches: list = field(default_factory=list)
    summary: str = ""

    # Görev 2 sonuçları
    draft_text: str = ""
    draft_type: str = ""
    routing_suggestion: dict = field(default_factory=dict)
    user_notifications: list = field(default_factory=list)

    # Meta
    errors: list = field(default_factory=list)
    processing_steps: list = field(default_factory=list)


class OrchestratorAgent:
    """
    Ana orkestratör agent.

    Tüm alt agent'ları yönetir ve evrak işleme iş akışını koordine eder.
    İki ana görev bloğunu sırayla çalıştırır:
      - Görev 1: Evrak Sınıflandırma ve İçerik Analizi
      - Görev 2: Resmi Yazı Taslaklama ve Birim Yönlendirme
    """

    def __init__(self) -> None:
        """Orkestratör agent'ı başlatır ve alt agent'ları yükler."""
        self.agents: dict[str, Any] = {}
        self.state = AgentState()
        logger.info("Orkestratör agent başlatıldı.")
        self._load_agents()

    def _load_agents(self) -> None:
        """Alt agent'ları yükler ve kaydeder."""
        from src.agents.ocr_agent import OCRAgent
        from src.agents.classification_agent import ClassificationAgent
        from src.agents.info_extraction_agent import InfoExtractionAgent
        from src.agents.missing_info_agent import MissingInfoAgent
        from src.agents.legislation_agent import LegislationAgent
        from src.agents.summarization_agent import SummarizationAgent
        from src.agents.draft_writer_agent import DraftWriterAgent
        from src.agents.routing_agent import RoutingAgent
        from src.agents.user_info_agent import UserInfoAgent

        self.agents = {
            "ocr": OCRAgent(),
            "classification": ClassificationAgent(),
            "info_extraction": InfoExtractionAgent(),
            "missing_info": MissingInfoAgent(),
            "legislation": LegislationAgent(),
            "summarization": SummarizationAgent(),
            "draft_writer": DraftWriterAgent(),
            "routing": RoutingAgent(),
            "user_info": UserInfoAgent(),
        }
        logger.info(f"{len(self.agents)} alt agent yüklendi.")

    def process(self, input_file: str, mode: str = "full") -> dict:
        """
        Evrak işleme sürecini başlatır.

        Args:
            input_file: İşlenecek evrak dosya yolu
            mode: Çalışma modu ('full', 'classify', 'draft')

        Returns:
            Tüm işlem sonuçlarını içeren sözlük
        """
        self.state = AgentState(input_file=input_file)
        logger.info(f"Evrak işleme başlatıldı: {input_file} (mod: {mode})")

        try:
            # Adım 1: OCR — Metin çıkarımı
            self._run_step("ocr", "OCR ile metin çıkarımı")

            if mode in ("full", "classify"):
                # GÖREV 1: Evrak Sınıflandırma ve İçerik Analizi
                self._run_step("classification", "Evrak sınıflandırma")
                self._run_step("info_extraction", "Bilgi çıkarma")
                self._run_step("missing_info", "Eksik bilgi tespiti")
                self._run_step("legislation", "Mevzuat eşleştirme")
                self._run_step("summarization", "Özet oluşturma")

            if mode in ("full", "draft"):
                # GÖREV 2: Resmi Yazı Taslaklama ve Birim Yönlendirme
                self._run_step("draft_writer", "Yazı taslağı oluşturma")
                self._run_step("routing", "Birim yönlendirme")
                self._run_step("user_info", "Kullanıcı bilgilendirme")

        except Exception as e:
            logger.error(f"İşlem sırasında hata: {e}")
            self.state.errors.append(str(e))

        return self._compile_results()

    def _run_step(self, agent_name: str, description: str) -> None:
        """
        Tek bir agent adımını çalıştırır.

        Args:
            agent_name: Çalıştırılacak agent'ın adı
            description: Adım açıklaması (loglama için)
        """
        logger.info(f"▶ {description}...")
        agent = self.agents.get(agent_name)

        if agent is None:
            logger.warning(f"Agent bulunamadı: {agent_name}")
            return

        try:
            result = agent.run(self.state)
            self.state.processing_steps.append({
                "agent": agent_name,
                "description": description,
                "status": "success",
            })
            logger.info(f"✓ {description} tamamlandı.")
        except Exception as e:
            self.state.processing_steps.append({
                "agent": agent_name,
                "description": description,
                "status": "error",
                "error": str(e),
            })
            self.state.errors.append(f"{agent_name}: {e}")
            logger.error(f"✗ {description} sırasında hata: {e}")

    def _compile_results(self) -> dict:
        """Tüm sonuçları derleyerek tek bir sözlük döndürür."""
        return {
            "input_file": self.state.input_file,
            "siniflandirma": self.state.classification,
            "bilgi_cikarim": self.state.extracted_info,
            "eksik_bilgiler": self.state.missing_info,
            "mevzuat_eslestirme": self.state.legislation_matches,
            "ozet": self.state.summary,
            "yazi_taslagi": self.state.draft_text,
            "yazi_turu": self.state.draft_type,
            "yonlendirme": self.state.routing_suggestion,
            "bilgilendirmeler": self.state.user_notifications,
            "islem_adimlari": self.state.processing_steps,
            "hatalar": self.state.errors,
        }
