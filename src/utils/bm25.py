"""
BM25-Okapi tabanlı saf Python metin arama yardımcıları.

Ağır bağımlılık (rank_bm25, sklearn vb.) gerektirmeden mevzuat
korpusu üzerinde anahtar kelime tabanlı sıralama sağlar. Mevzuat
Eşleştirme Agent'ının RAG geri getirme (retrieval) katmanıdır.

Şartname Referansı (Görev 1):
    "İlgili mevzuat, yönetmelik veya standart yazışma kurallarını önerebilme"
"""

from __future__ import annotations

import math
import re
from typing import Dict, List

from src.utils.turkish_nlp import TURKCE_DURAK_KELIMELERI, turkish_lower

# Türkçe karakterleri (şapkalı ünlüler dahil: malî, resmî) ve rakamları kapsayan token deseni
_TOKEN_DESENI = re.compile(r"[a-zçğıöşüâîû0-9]+")


def tokenize(text: str) -> List[str]:
    """
    Metni BM25 için token listesine dönüştürür.

    Adımlar: Türkçe'ye uygun küçük harf dönüşümü (turkish_lower),
    noktalama temizliği (harf/rakam dışı karakterlerde bölme),
    durak kelime (stopword) çıkarma ve 2+ karakter filtresi.
    """
    lowered = turkish_lower(text)
    tokens = _TOKEN_DESENI.findall(lowered)
    return [t for t in tokens if len(t) >= 2 and t not in TURKCE_DURAK_KELIMELERI]


class BM25Okapi:
    """
    BM25-Okapi sıralama fonksiyonunun saf Python gerçeklemesi.

    Kullanım:
        bm25 = BM25Okapi([tokenize(d) for d in belgeler])
        skorlar = bm25.get_scores(tokenize(sorgu))

    IDF formülü: log((N - df + 0.5) / (df + 0.5) + 1)  (negatif olmayan varyant)
    """

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75) -> None:
        """
        Args:
            corpus: Tokenize edilmiş belgeler listesi.
            k1: Terim frekansı doygunluk parametresi.
            b: Belge uzunluğu normalizasyon parametresi.
        """
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens: List[int] = [len(doc) for doc in corpus]
        self.avgdl: float = (
            sum(self.doc_lens) / self.corpus_size if self.corpus_size else 0.0
        )

        # Belge başına terim frekansları ve korpus geneli belge frekansları
        self.doc_freqs: List[Dict[str, int]] = []
        df: Dict[str, int] = {}
        for doc in corpus:
            freqs: Dict[str, int] = {}
            for token in doc:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)
            for token in freqs:
                df[token] = df.get(token, 0) + 1

        self.idf: Dict[str, float] = {
            token: math.log((self.corpus_size - n + 0.5) / (n + 0.5) + 1.0)
            for token, n in df.items()
        }

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        """
        Sorgu token'ları için korpustaki her belgenin BM25 skorunu döndürür.

        Returns:
            Korpus sırasıyla hizalı skor listesi (yüksek skor = daha ilgili).
        """
        scores = [0.0] * self.corpus_size
        if not self.corpus_size or not query_tokens:
            return scores

        for token in query_tokens:
            idf = self.idf.get(token)
            if idf is None:
                continue
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(token, 0)
                if tf == 0:
                    continue
                if self.avgdl > 0:
                    norm = self.k1 * (1 - self.b + self.b * self.doc_lens[i] / self.avgdl)
                else:
                    norm = self.k1
                scores[i] += idf * tf * (self.k1 + 1) / (tf + norm)

        return scores
