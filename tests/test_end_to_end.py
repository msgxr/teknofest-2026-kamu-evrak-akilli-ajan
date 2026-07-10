"""
Uçtan uca entegrasyon testleri.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import OrchestratorAgent, AgentState


class TestEndToEnd:
    """Uçtan uca entegrasyon testleri."""

    def test_orchestrator_initialization(self):
        """Orkestratör tüm agent'ları yüklemeli."""
        orchestrator = OrchestratorAgent()
        expected_agents = [
            "ocr", "classification", "info_extraction",
            "missing_info", "legislation", "summarization",
            "draft_writer", "routing", "user_info",
        ]
        for agent_name in expected_agents:
            assert agent_name in orchestrator.agents, f"'{agent_name}' agent yüklenmemiş"

    def test_process_text_file(self):
        """Metin dosyasını uçtan uca işleyebilmeli."""
        test_file = Path(__file__).parent.parent / "data" / "raw" / "kurgu_evraklar" / "ornek_dilekce.txt"

        if not test_file.exists():
            pytest.skip("Test dosyası bulunamadı")

        orchestrator = OrchestratorAgent()
        result = orchestrator.process(str(test_file), mode="full")

        # Sonuç yapısı kontrolü
        assert "siniflandirma" in result
        assert "bilgi_cikarim" in result
        assert "eksik_bilgiler" in result
        assert "ozet" in result
        assert "yonlendirme" in result
        assert "islem_adimlari" in result

    def test_classify_mode(self):
        """Sadece sınıflandırma modunda çalışabilmeli."""
        test_file = Path(__file__).parent.parent / "data" / "raw" / "kurgu_evraklar" / "ornek_dilekce.txt"

        if not test_file.exists():
            pytest.skip("Test dosyası bulunamadı")

        orchestrator = OrchestratorAgent()
        result = orchestrator.process(str(test_file), mode="classify")

        assert "siniflandirma" in result
        # Draft modu çalıştırılmamalı (classify modunda)
        assert result.get("yazi_turu") == ""

    def test_agent_state_initialization(self):
        """AgentState doğru başlatılmalı."""
        state = AgentState(input_file="test.txt")
        assert state.input_file == "test.txt"
        assert state.raw_text == ""
        assert state.classification == {}
        assert state.errors == []
        assert state.processing_steps == []
