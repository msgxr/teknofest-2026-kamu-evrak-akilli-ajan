"""
Opsiyonel semantik arama ve yeniden sıralama (rerank) katmanı.

Hibrit mevzuat RAG'inin opsiyonel yoğun (dense) yarısı: sentence-transformers
kuruluysa VE EMBEDDING_SEMANTIK_AKTIF=1 ise mevzuat bölümleri
`ytu-ce-cosmos/turkish-e5-large` ile gömülür ve sorguyla kosinüs
benzerliğine göre aday bölümler bulunur. EMBEDDING_RERANK_AKTIF=1 ise
aday havuzu `BAAI/bge-reranker-v2-m3` çapraz kodlayıcısıyla yeniden
sıralanır. Hiçbir koşulda çekirdek BM25 yolu bozulmaz: kütüphane yok /
ayar kapalı / model indirilemedi durumlarının tümünde bu modül zarifçe
devre dışı kalır (offline-first ilkesi).

Model kullanım biçimleri model kartlarından doğrulanmıştır:
- turkish-e5-large instruct-taban olduğundan sorgular
  "Instruct: {görev}\\nQuery: {sorgu}" biçiminde, pasajlar ÖNEKSİZ ve
  normalize_embeddings=True ile kodlanır.
- bge-reranker-v2-m3, sentence-transformers CrossEncoder ile yüklenir;
  logit çıktısı sigmoid ile [0-1] aralığına taşınır.

Şartname Referansı (Görev 1):
    "İlgili mevzuat, yönetmelik veya standart yazışma kurallarını önerebilme"
"""

from __future__ import annotations

import importlib.util
import logging
import math
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("kamu_evrak_ajan.semantik_arama")

# turkish-e5-large model kartındaki geri getirme görev tanımı (İngilizce
# talimat, modelin eğitildiği biçimdir; sorgu/pasaj metinleri Türkçedir)
E5_SORGU_GOREVI = (
    "Given a Turkish search query, retrieve relevant passages "
    "written in Turkish that best answer the query"
)


def puan_birlestir(
    bm25_puanlari: Dict[int, float],
    dense_puanlari: Dict[int, float],
    bm25_agirlik: float = 0.6,
) -> Dict[int, float]:
    """
    Normalize edilmiş BM25 ve semantik puanları dışbükey ağırlıkla birleştirir.

    Saf Python'dur ve ağır bağımlılık gerektirmez (birim testlenebilir).
    Her iki sözlük de {chunk_indeksi: [0-1] normalize puan} biçimindedir;
    bir tarafta bulunmayan indeks o tarafta 0 sayılır. Taraflardan biri
    boşsa diğeri olduğu gibi döner (tek kaynaklı arama davranışı korunur).

    Args:
        bm25_puanlari: BM25 tarafının normalize puanları
        dense_puanlari: Semantik tarafın normalize puanları
        bm25_agirlik: BM25 tarafının ağırlığı (0-1; kalan semantiğe gider)

    Returns:
        {chunk_indeksi: birleşik puan}
    """
    if not dense_puanlari:
        return dict(bm25_puanlari)
    if not bm25_puanlari:
        return dict(dense_puanlari)
    dense_agirlik = 1.0 - bm25_agirlik
    anahtarlar = set(bm25_puanlari) | set(dense_puanlari)
    return {
        i: bm25_agirlik * bm25_puanlari.get(i, 0.0)
        + dense_agirlik * dense_puanlari.get(i, 0.0)
        for i in anahtarlar
    }


def rrf_birlestir(
    siralamalar: Sequence[Dict[int, float]],
    k: int = 60,
) -> Dict[int, float]:
    """Birden çok puanlama listesini Reciprocal Rank Fusion (RRF) ile birleştirir.

    Her liste {chunk_indeksi: puan}; her liste kendi içinde puana göre azalan
    sıralanıp her belgeye 1/(k + sıra) katkısı verilir (sıra 1'den başlar) ve
    katkılar toplanır. RRF **ölçek-bağımsızdır**: farklı dağılımlı BM25-mutlak
    ile dense-kosinüs skorlarını doğrudan toplamanın (puan_birlestir) yol açtığı
    ölçek uyumsuzluğunu çözer; yalnızca SIRALAMA bilgisini kullanır. Böylece
    mutlak benzerlik değerleri etik/atıf doğrulaması için ayrıca korunabilir.

    Tek liste (ör. yalnızca BM25) verilirse o listenin sırasını birebir korur —
    offline çekirdek davranışı bozulmaz.

    Literatür: Cormack, Clarke, Büttcher (2009) "Reciprocal Rank Fusion
    outperforms Condorcet and individual Rank Learning Methods" (SIGIR);
    k=60 alan standardı varsayılandır (Elasticsearch/Vespa/Weaviate).

    Args:
        siralamalar: {chunk_indeksi: puan} sözlüklerinin listesi (boş olanlar atlanır)
        k: RRF yumuşatma sabiti (yüksek k → sıra farklarını yumuşatır)

    Returns:
        {chunk_indeksi: rrf_skoru} — yüksek skor daha ilgili
    """
    dolu = [s for s in siralamalar if s]
    if not dolu:
        return {}
    birlesik: Dict[int, float] = {}
    for puanlar in dolu:
        sirali = sorted(puanlar.items(), key=lambda kv: kv[1], reverse=True)
        for sira, (idx, _) in enumerate(sirali, start=1):
            birlesik[idx] = birlesik.get(idx, 0.0) + 1.0 / (k + sira)
    return birlesik


def _ayarlar():
    """Ayar nesnesini hata toleranslı döndürür (import döngüsünden kaçınır)."""
    try:
        from src.config import settings

        return settings.embedding
    except Exception as e:  # ayar katmanı yoksa opsiyonel katman kapalı kalır
        logger.warning(f"Embedding ayarları okunamadı, semantik katman kapalı: {e}")
        return None


class SemantikArama:
    """
    turkish-e5-large ile bellek içi yoğun (dense) mevzuat araması.

    Kullanım (LegislationAgent içinden):
        sa = SemantikArama()
        if sa.aktif() and sa.indeksle(bolum_metinleri):
            adaylar = sa.ara(sorgu, top_n=10)   # [(chunk_indeksi, kosinüs)]
    """

    def __init__(self, model_adi: Optional[str] = None) -> None:
        self._model_adi = model_adi
        self._model = None
        self._gomme = None  # indekslenen bölümlerin normalize gömme matrisi
        self._hata = False

    def aktif(self) -> bool:
        """Katman kullanılabilir mi? (ayar açık + kütüphane kurulu + hatasız)"""
        if self._hata:
            return False
        ayar = _ayarlar()
        if ayar is None or not ayar.semantik_aktif:
            return False
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> None:
        """Modeli (bir kez) yüklemeyi dener; her hata katmanı devre dışı bırakır."""
        if self._model is not None or self._hata:
            return
        try:
            from sentence_transformers import SentenceTransformer

            ayar = _ayarlar()
            adi = self._model_adi or (ayar.semantik_model if ayar else "")
            self._model = SentenceTransformer(adi)
            logger.info(f"Semantik arama modeli yüklendi: {adi}")
        except Exception as e:
            self._hata = True
            logger.warning(f"Semantik model yüklenemedi, BM25'e düşülüyor: {e}")

    def indeksle(self, metinler: Sequence[str]) -> bool:
        """
        Bölüm metinlerini gömerek bellek içi indeksi kurar.

        Pasajlar model kartına uygun olarak ÖNEKSİZ kodlanır.

        Returns:
            İndeks kurulduysa True; katman kullanılamıyorsa False.
        """
        if not metinler or not self.aktif():
            return False
        self._ensure_model()
        if self._model is None:
            return False
        try:
            self._gomme = self._model.encode(
                list(metinler), normalize_embeddings=True
            )
            logger.info(f"Semantik indeks kuruldu: {len(metinler)} bölüm.")
            return True
        except Exception as e:
            self._hata = True
            self._gomme = None
            logger.warning(f"Semantik indeksleme başarısız, BM25'e düşülüyor: {e}")
            return False

    def ara(self, sorgu: str, top_n: int = 10) -> List[Tuple[int, float]]:
        """
        Sorguya en yakın bölümleri döndürür.

        Returns:
            [(chunk_indeksi, kosinüs_benzerliği)] — pozitif benzerlikler,
            azalan sırada, en fazla top_n adet. Katman kullanılamıyorsa [].
        """
        if self._gomme is None or self._model is None or self._hata:
            return []
        try:
            sorgu_metni = f"Instruct: {E5_SORGU_GOREVI}\nQuery: {sorgu}"
            sorgu_gomme = self._model.encode([sorgu_metni], normalize_embeddings=True)[0]
            skorlar = self._gomme @ sorgu_gomme  # normalize gömmede iç çarpım = kosinüs
            sirali = skorlar.argsort()[::-1][:top_n]
            return [
                (int(i), float(skorlar[i])) for i in sirali if float(skorlar[i]) > 0.0
            ]
        except Exception as e:
            self._hata = True
            logger.warning(f"Semantik arama başarısız, BM25'e düşülüyor: {e}")
            return []


class YenidenSiralayici:
    """
    bge-reranker-v2-m3 ile (sorgu, pasaj) çiftlerini yeniden puanlar.

    Çapraz kodlayıcı logit üretir; sigmoid ile [0-1] aralığına taşınır ki
    hibrit akıştaki normalize puanlarla aynı ölçekte kullanılabilsin.
    """

    def __init__(self, model_adi: Optional[str] = None) -> None:
        self._model_adi = model_adi
        self._model = None
        self._hata = False

    def aktif(self) -> bool:
        """Katman kullanılabilir mi? (ayar açık + kütüphane kurulu + hatasız)"""
        if self._hata:
            return False
        ayar = _ayarlar()
        if ayar is None or not ayar.rerank_aktif:
            return False
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> None:
        """Çapraz kodlayıcıyı (bir kez) yüklemeyi dener."""
        if self._model is not None or self._hata:
            return
        try:
            from sentence_transformers import CrossEncoder

            ayar = _ayarlar()
            adi = self._model_adi or (ayar.rerank_model if ayar else "")
            self._model = CrossEncoder(adi)
            logger.info(f"Yeniden sıralama modeli yüklendi: {adi}")
        except Exception as e:
            self._hata = True
            logger.warning(f"Rerank modeli yüklenemedi, bu adım atlanıyor: {e}")

    def sirala(self, sorgu: str, metinler: Sequence[str]) -> Optional[List[float]]:
        """
        Adayları yeniden puanlar.

        Returns:
            metinler ile hizalı [0-1] puan listesi; katman kullanılamıyorsa None.
        """
        if not metinler or not self.aktif():
            return None
        self._ensure_model()
        if self._model is None:
            return None
        try:
            logitler = self._model.predict([(sorgu, m) for m in metinler])
            return [1.0 / (1.0 + math.exp(-float(x))) for x in logitler]
        except Exception as e:
            self._hata = True
            logger.warning(f"Yeniden sıralama başarısız, bu adım atlanıyor: {e}")
            return None
