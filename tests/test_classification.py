"""
Sınıflandırma Agent testleri.
"""

import pytest
import sys
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.classification_agent import ClassificationAgent, EVRAK_TURLERI
from src.agents.orchestrator import AgentState


class TestClassificationAgent:
    """Sınıflandırma Agent birim testleri."""

    def setup_method(self):
        """Her test öncesi agent'ı kural tabanlı modda başlat."""
        self.agent = ClassificationAgent(method="rule_based")

    def test_dilekce_classification(self):
        """Dilekçe metnini doğru sınıflandırmalı."""
        state = AgentState(raw_text="""
        Sayın Müdürlüğünüze,
        Bu dilekçe ile talebimi bildirmek istiyorum.
        Başvurumun değerlendirilmesini rica ederim.
        Arz ederim.
        """)

        result = self.agent.run(state)
        assert result.classification["tur"] == "dilekce"
        assert result.classification["guven"] > 0

    def test_ust_yazi_classification(self):
        """Üst yazı metnini doğru sınıflandırmalı."""
        state = AgentState(raw_text="""
        T.C.
        Bilişim Vadisi Başkanlığı
        İlgi: 05/01/2026 tarihli yazı
        Ekte sunulmuştur.
        Makamınıza arz ederim.
        """)

        result = self.agent.run(state)
        assert result.classification["tur"] == "ust_yazi"

    def test_tutanak_classification(self):
        """Tutanak metnini doğru sınıflandırmalı."""
        state = AgentState(raw_text="""
        TOPLANTI TUTANAĞI
        Toplantı tarihi: 08/07/2026
        Katılımcılar: Dr. Mehmet Kaya, Ayşe Demir
        Gündem: Personel alım planı
        """)

        result = self.agent.run(state)
        assert result.classification["tur"] == "tutanak"

    def test_empty_text(self):
        """Boş metin durumunda 'bilinmiyor' döndürmeli."""
        state = AgentState(raw_text="")
        result = self.agent.run(state)
        assert result.classification["tur"] == "bilinmiyor"
        assert result.classification["guven"] == 0.0

    def test_evrak_turleri_defined(self):
        """Tüm evrak türleri tanımlı olmalı."""
        expected_types = [
            "dilekce", "ust_yazi", "cevap_yazisi", "bilgilendirme",
            "tutanak", "rapor", "genelge", "onayli_belge", "diger",
        ]
        for tur in expected_types:
            assert tur in EVRAK_TURLERI, f"'{tur}' evrak türü tanımlı değil"

    def test_classification_has_required_fields(self):
        """Sınıflandırma sonucu gerekli alanları içermeli."""
        state = AgentState(raw_text="Test metni dilekçe başvuru arz ederim")
        result = self.agent.run(state)

        required_fields = ["tur", "tur_adi", "guven", "aciklama"]
        for field in required_fields:
            assert field in result.classification, f"'{field}' alanı eksik"


class TestMissingInfoAgent:
    """Eksik Bilgi Agent birim testleri."""

    def test_missing_info_detection(self):
        """Eksik bilgi tespit etmeli."""
        from src.agents.missing_info_agent import MissingInfoAgent

        agent = MissingInfoAgent()
        state = AgentState(
            raw_text="Kısa metin",
            classification={"tur": "dilekce"},
            extracted_info={"tarihler": [], "konu": "", "muhatap": ""},
        )

        result = agent.run(state)
        assert len(result.missing_info) > 0


class TestInfoExtractionAgent:
    """Bilgi Çıkarım Agent birim testleri."""

    def test_date_extraction(self):
        """Tarih bilgisini çıkarmalı."""
        from src.agents.info_extraction_agent import InfoExtractionAgent

        agent = InfoExtractionAgent()
        state = AgentState(raw_text="Tarih: 10/07/2026 tarihinde toplantı yapılmıştır.")

        result = agent.run(state)
        assert len(result.extracted_info["tarihler"]) > 0

    def test_subject_extraction(self):
        """Konu bilgisini çıkarmalı."""
        from src.agents.info_extraction_agent import InfoExtractionAgent

        agent = InfoExtractionAgent()
        state = AgentState(raw_text="Konu : Dijital Dönüşüm Eylem Planı\nMetin buradadır.")

        result = agent.run(state)
        assert "Dijital Dönüşüm" in result.extracted_info["konu"]


class TestRoutingAgent:
    """Yönlendirme Agent birim testleri."""

    def test_routing_suggestion(self):
        """Birim yönlendirme önerisi vermelidir."""
        from src.agents.routing_agent import RoutingAgent

        agent = RoutingAgent()
        state = AgentState(
            raw_text="Personel atama ve terfi işlemleri hakkında bilgi talebi",
            classification={"tur": "dilekce"},
            extracted_info={},
        )

        result = agent.run(state)
        assert result.routing_suggestion.get("birim") is not None
        assert result.routing_suggestion.get("guven") > 0
