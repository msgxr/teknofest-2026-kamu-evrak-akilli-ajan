"""
Mevzuat Eşleştirme Agent — İlgili mevzuat önerisi.

RAG (Retrieval Augmented Generation) tabanlı mevzuat eşleştirme.

Şartname Referansı (Görev 1):
    "İlgili mevzuat, yönetmelik veya standart yazışma kurallarını önerebilme"
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.legislation")


class LegislationAgent:
    """
    Mevzuat eşleştirme agent'ı.

    Evrak içeriğine göre ilgili mevzuat, yönetmelik ve standart
    yazışma kurallarını önerir. ChromaDB vektör veritabanı ile
    RAG yaklaşımı kullanır.
    """

    def __init__(self) -> None:
        self.db = None
        logger.info("Mevzuat Agent başlatıldı.")

    def _init_vector_db(self) -> None:
        """Vektör veritabanını başlatır."""
        try:
            import chromadb
            from src.config import settings

            self.client = chromadb.PersistentClient(path=settings.chroma.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=settings.chroma.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Mevzuat veritabanı yüklendi: {self.collection.count()} kayıt")
        except ImportError:
            logger.warning("ChromaDB yüklü değil, mevzuat eşleştirme devre dışı.")
            self.collection = None

    def run(self, state: "AgentState") -> "AgentState":
        """Evrak içeriğine göre mevzuat önerir."""
        text = state.raw_text
        evrak_turu = state.classification.get("tur", "")

        # Vektör DB ile eşleştirme dene
        if self.collection is None:
            self._init_vector_db()

        if self.collection and self.collection.count() > 0:
            matches = self._search_vector_db(text)
        else:
            # Fallback: Kural tabanlı eşleştirme
            matches = self._rule_based_match(text, evrak_turu)

        state.legislation_matches = matches
        logger.info(f"Mevzuat eşleştirmesi: {len(matches)} sonuç")
        return state

    def _search_vector_db(self, text: str) -> list[dict]:
        """Vektör veritabanında arama yapar."""
        try:
            results = self.collection.query(
                query_texts=[text[:1000]],
                n_results=5,
            )

            matches = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    matches.append({
                        "baslik": results["metadatas"][0][i].get("baslik", f"Mevzuat #{i+1}"),
                        "icerik_ozeti": doc[:300],
                        "benzerlik": 1 - results["distances"][0][i] if results["distances"] else 0,
                        "kaynak": results["metadatas"][0][i].get("kaynak", ""),
                    })
            return matches

        except Exception as e:
            logger.error(f"Vektör DB arama hatası: {e}")
            return []

    def _rule_based_match(self, text: str, evrak_turu: str) -> list[dict]:
        """Kural tabanlı mevzuat eşleştirme (fallback)."""
        # Temel mevzuat referansları
        base_regulations = [
            {
                "baslik": "Resmi Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik",
                "aciklama": "Tüm resmi yazışmalarda uyulması gereken format ve usul kuralları",
                "kaynak": "Cumhurbaşkanlığı Kararnamesi - Resmi Gazete",
                "ilgili_turler": ["ust_yazi", "cevap_yazisi", "bilgilendirme", "genelge"],
            },
            {
                "baslik": "Dilekçe Hakkı Kanunu (3071 Sayılı Kanun)",
                "aciklama": "Vatandaşların dilekçe hakkı ve dilekçe usulü",
                "kaynak": "mevzuat.gov.tr",
                "ilgili_turler": ["dilekce"],
            },
            {
                "baslik": "Bilgi Edinme Hakkı Kanunu (4982 Sayılı Kanun)",
                "aciklama": "Vatandaşların bilgi edinme hakkı ve başvuru usulü",
                "kaynak": "mevzuat.gov.tr",
                "ilgili_turler": ["dilekce", "bilgilendirme"],
            },
            {
                "baslik": "Devlet Arşiv Hizmetleri Hakkında Yönetmelik",
                "aciklama": "Evrak arşivleme ve saklama usulleri",
                "kaynak": "mevzuat.gov.tr",
                "ilgili_turler": ["ust_yazi", "tutanak", "rapor"],
            },
            {
                "baslik": "Elektronik İmza Kanunu (5070 Sayılı Kanun)",
                "aciklama": "Elektronik imza ve elektronik belge düzenlemeleri",
                "kaynak": "mevzuat.gov.tr",
                "ilgili_turler": ["onayli_belge", "ust_yazi", "cevap_yazisi"],
            },
        ]

        matches = []
        for reg in base_regulations:
            if evrak_turu in reg["ilgili_turler"] or not evrak_turu:
                matches.append({
                    "baslik": reg["baslik"],
                    "icerik_ozeti": reg["aciklama"],
                    "kaynak": reg["kaynak"],
                    "benzerlik": 0.8 if evrak_turu in reg["ilgili_turler"] else 0.3,
                })

        return sorted(matches, key=lambda x: x["benzerlik"], reverse=True)

    def index_legislation(self, documents: list[dict]) -> None:
        """
        Mevzuat belgelerini vektör veritabanına indeksler.

        Args:
            documents: İndekslenecek belgeler [{baslik, metin, kaynak}, ...]
        """
        if self.collection is None:
            self._init_vector_db()

        if self.collection is None:
            logger.error("Vektör DB başlatılamadı, indeksleme yapılamıyor.")
            return

        ids = [f"mevzuat_{i}" for i in range(len(documents))]
        texts = [d["metin"] for d in documents]
        metadatas = [{"baslik": d["baslik"], "kaynak": d.get("kaynak", "")} for d in documents]

        self.collection.add(documents=texts, metadatas=metadatas, ids=ids)
        logger.info(f"{len(documents)} mevzuat belgesi indekslendi.")
