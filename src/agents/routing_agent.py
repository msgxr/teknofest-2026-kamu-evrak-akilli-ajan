"""
Birim Yönlendirme Agent — Evrakı doğru birime yönlendirme.

Şartname Referansı (Görev 2):
    "Evrakın içeriğine göre doğru birime yönlendirme önerisinde bulunması"
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.routing")

# Kamu kurumlarında tipik birim yapısı
BIRIMLER = {
    "yazi_isleri": {
        "ad": "Yazı İşleri Müdürlüğü",
        "gorev_alani": ["yazışma", "evrak", "arşiv", "dosyalama", "kayıt"],
        "aciklama": "Genel yazışma ve evrak yönetimi",
    },
    "hukuk": {
        "ad": "Hukuk Müşavirliği",
        "gorev_alani": ["hukuk", "dava", "mevzuat", "kanun", "yönetmelik", "mahkeme", "itiraz"],
        "aciklama": "Hukuki konular ve mevzuat danışmanlığı",
    },
    "insan_kaynaklari": {
        "ad": "İnsan Kaynakları Müdürlüğü",
        "gorev_alani": ["personel", "atama", "terfi", "izin", "sicil", "özlük", "emeklilik"],
        "aciklama": "Personel işlemleri ve özlük hakları",
    },
    "mali_hizmetler": {
        "ad": "Mali Hizmetler Müdürlüğü",
        "gorev_alani": ["bütçe", "ödeme", "mali", "finans", "harcama", "gelir", "vergi"],
        "aciklama": "Mali işlemler ve bütçe yönetimi",
    },
    "bilgi_islem": {
        "ad": "Bilgi İşlem Müdürlüğü",
        "gorev_alani": ["bilişim", "yazılım", "sistem", "ağ", "güvenlik", "teknoloji"],
        "aciklama": "Bilgi teknolojileri ve dijital altyapı",
    },
    "strateji": {
        "ad": "Strateji Geliştirme Dairesi",
        "gorev_alani": ["strateji", "planlama", "performans", "kalite", "istatistik"],
        "aciklama": "Stratejik planlama ve kurumsal performans",
    },
    "basin_halkla_iliskiler": {
        "ad": "Basın ve Halkla İlişkiler Müdürlüğü",
        "gorev_alani": ["basın", "medya", "halkla ilişkiler", "şikayet", "vatandaş", "dilekçe"],
        "aciklama": "Basın ilişkileri ve vatandaş başvuruları",
    },
    "destek_hizmetleri": {
        "ad": "Destek Hizmetleri Müdürlüğü",
        "gorev_alani": ["ihale", "satınalma", "lojistik", "taşınır", "bakım", "onarım"],
        "aciklama": "Satınalma, ihale ve destek hizmetleri",
    },
    "genel_mudurluk": {
        "ad": "Genel Müdürlük",
        "gorev_alani": ["üst düzey", "makam", "onay", "direktif"],
        "aciklama": "Üst yönetim kararları",
    },
}


class RoutingAgent:
    """
    Birim yönlendirme agent'ı.

    Evrak içeriğini analiz ederek hangi birime yönlendirilmesi
    gerektiğini belirler ve gerekçe sunar.
    """

    def __init__(self) -> None:
        logger.info("Yönlendirme Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evrakı uygun birime yönlendirir."""
        text = state.raw_text
        evrak_turu = state.classification.get("tur", "")
        extracted = state.extracted_info

        # Yönlendirme önerisi oluştur
        suggestion = self._determine_routing(text, evrak_turu, extracted)
        state.routing_suggestion = suggestion

        logger.info(
            f"Yönlendirme önerisi: {suggestion.get('birim', 'Belirsiz')} "
            f"(güven: {suggestion.get('guven', 0):.2f})"
        )
        return state

    def _determine_routing(self, text: str, evrak_turu: str, extracted: dict) -> dict:
        """Evrak için yönlendirme önerisi oluşturur."""
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for birim_key, birim_info in BIRIMLER.items():
            score = 0.0
            for keyword in birim_info["gorev_alani"]:
                if keyword.lower() in text_lower:
                    score += 1.0

            # Evrak türüne göre bonus
            score += self._type_bonus(evrak_turu, birim_key)
            scores[birim_key] = score

        if not scores or max(scores.values()) == 0:
            return {
                "birim": "Yazı İşleri Müdürlüğü",
                "birim_kodu": "yazi_isleri",
                "gerekce": "Evrak içeriğine göre belirli bir birim tespit edilemedi, genel yazışma birimi olarak yönlendirildi.",
                "guven": 0.3,
                "alternatifler": [],
            }

        # En yüksek skora sahip birimi bul
        best_birim = max(scores, key=scores.get)
        best_info = BIRIMLER[best_birim]
        max_score = scores[best_birim]

        # Alternatif birimleri bul
        sorted_birimler = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        alternatifler = [
            {"birim": BIRIMLER[k]["ad"], "skor": v}
            for k, v in sorted_birimler[1:4]
            if v > 0
        ]

        # Güven skoru hesapla
        total = sum(scores.values())
        guven = max_score / total if total > 0 else 0.3

        return {
            "birim": best_info["ad"],
            "birim_kodu": best_birim,
            "gerekce": f"Evrak içeriği '{best_info['aciklama']}' kapsamında değerlendirilmiştir.",
            "guven": min(guven, 1.0),
            "alternatifler": alternatifler,
        }

    def _type_bonus(self, evrak_turu: str, birim_key: str) -> float:
        """Evrak türüne göre birim bonusu verir."""
        bonuses = {
            ("dilekce", "basin_halkla_iliskiler"): 2.0,
            ("dilekce", "yazi_isleri"): 1.0,
            ("tutanak", "hukuk"): 1.5,
            ("rapor", "strateji"): 1.5,
            ("genelge", "genel_mudurluk"): 2.0,
            ("onayli_belge", "genel_mudurluk"): 1.5,
        }
        return bonuses.get((evrak_turu, birim_key), 0.0)
