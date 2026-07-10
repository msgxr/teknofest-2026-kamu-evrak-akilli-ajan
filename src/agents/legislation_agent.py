"""
Mevzuat Eşleştirme Agent — BM25 tabanlı RAG ile ilgili mevzuat önerisi.

data/raw/mevzuat_metinleri/ altındaki mevzuat özet dosyalarını bölüm
bazında parçalara (chunk) ayırır, saf Python BM25-Okapi indeksiyle
bellekte arar ve evraka en uygun mevzuat hükümlerini önerir. ChromaDB
kuruluysa opsiyonel semantik arama denenir; hiçbir yol sonuç üretemezse
kural tabanlı eşleştirmeye düşülür (LLM'siz/offline tam çalışma).

Şartname Referansı (Görev 1):
    "İlgili mevzuat, yönetmelik veya standart yazışma kurallarını önerebilme"
"""

from __future__ import annotations

import importlib.util
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from src.utils.bm25 import BM25Okapi, tokenize
from src.utils.turkish_nlp import turkish_lower

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.legislation")

# Şartname: yazışma türü evraklarda standart yazışma kuralları da önerilmeli
YAZISMA_TURLERI = {"ust_yazi", "cevap_yazisi", "bilgilendirme", "genelge"}

# Resmî Yazışma Yönetmeliği korpus dosyasının kimliği (dosya adı gövdesi)
RESMI_YAZISMA_DOC_ID = "resmi_yazisma_yonetmeligi"

# Evrak türü → o türü doğrudan DÜZENLEYEN usul mevzuatı (doc_id).
# Bu mevzuatın önerilerin başında yer alması sözcük çakışmasından değil
# türün kendisinden gelir: her resmî yazışma Resmî Yazışma Yönetmeliğine,
# her dilekçe 3071 sayılı Kanuna tabidir (alan mevzuatı içerikle yarışır,
# usul mevzuatı tanım gereği geçerlidir).
TUR_USUL_MEVZUATI: Dict[str, str] = {
    tur: RESMI_YAZISMA_DOC_ID for tur in YAZISMA_TURLERI
}
TUR_USUL_MEVZUATI["dilekce"] = "dilekce_hakki_kanunu_3071"

# Sorguya dahil edilecek ham metin uzunluğu ve özet uzunluğu
SORGU_METIN_LIMITI = 1500
OZET_LIMITI = 300

# ----------------------------------------------------------------------
# Tür-koşullu yeniden sıralama (re-ranking) ağırlıkları
#
# İlke: BM25 salt sözcük çakışmasına bakar; "park aydınlatması" ile
# KVKK'nın "aydınlatma yükümlülüğü" gibi eş sesli çakışmalar alan dışı
# mevzuatı öne çıkarabilir. BM25 skoru iki genel sinyalle ağırlıklandırılır:
#
#   1. TUR_MEVZUAT_AGIRLIKLARI: evrak türünü doğrudan DÜZENLEYEN usul
#      mevzuatına tür bazlı öncelik çarpanı (ör. dilekçe → 3071 sayılı
#      Kanun; onaylı belge → 5070 sayılı Kanun).
#   2. MEVZUAT_TEMALARI + ALAN_MEVZUATI: alan mevzuatı (657, 4734, 5018,
#      KVKK ...) ancak belgede o alanın söz dağarcığından EN AZ İKİ farklı
#      tetikleyici kök geçiyorsa güçlenir (TEMA_BONUSU); geçmiyorsa
#      çakışma tesadüfi sayılır ve skor ALAN_DISI_SONUMLEME ile düşürülür.
#
# Çarpanlar belge/veri kümesine değil tür-tema düzeyine bağlı genel
# değerlerdir; yeni mevzuat dosyası eklendiğinde yalnızca bu tablolara
# doc_id (dosya adı gövdesi) kaydı eklemek yeterlidir.
# ----------------------------------------------------------------------

TUR_MEVZUAT_AGIRLIKLARI: Dict[str, Dict[str, float]] = {
    "dilekce": {
        "dilekce_hakki_kanunu_3071": 1.4,
        "bilgi_edinme_kanunu_4982": 1.2,
        "cimer_vatandas_basvurulari_bilgi_notu": 1.2,
    },
    "cevap_yazisi": {
        "resmi_yazisma_yonetmeligi": 1.2,
        "dilekce_hakki_kanunu_3071": 1.15,
        "cimer_vatandas_basvurulari_bilgi_notu": 1.15,
    },
    "ust_yazi": {
        "resmi_yazisma_yonetmeligi": 1.2,
        "e_yazisma_teknik_rehberi_bilgi_notu": 1.1,
    },
    "bilgilendirme": {"resmi_yazisma_yonetmeligi": 1.2},
    "genelge": {"resmi_yazisma_yonetmeligi": 1.2},
    "tutanak": {"devlet_arsiv_hizmetleri_yonetmeligi": 1.1},
    "rapor": {"devlet_arsiv_hizmetleri_yonetmeligi": 1.1},
    "onayli_belge": {"elektronik_imza_kanunu_5070": 1.2},
}

# Tema → (tetikleyici kökler, o temanın alan mevzuatı doc_id'leri).
# Tetikleyiciler kök (önek) olarak aranır: "fatura" → "faturamın" da sayılır.
MEVZUAT_TEMALARI: Dict[str, Tuple[frozenset, frozenset]] = {
    "personel": (
        frozenset({"memur", "personel", "kadro", "atama", "intibak", "kademe",
                   "derece", "özlük", "disiplin", "terfi", "becayiş", "sicil", "657"}),
        frozenset({"devlet_memurlari_kanunu_657"}),
    ),
    "ihale": (
        frozenset({"ihale", "teklif", "şartname", "yüklenici", "sözleşme",
                   "istekli", "muayene", "hakediş", "4734"}),
        frozenset({"kamu_ihale_kanunu_4734"}),
    ),
    "mali": (
        frozenset({"bütçe", "ödenek", "harcama", "fatura", "tahakkuk", "tahsil",
                   "ödeme", "vergi", "iade", "muhasebe", "gider", "5018"}),
        frozenset({"kamu_mali_yonetimi_5018"}),
    ),
    "kisisel_veri": (
        frozenset({"kişisel", "kvkk", "rıza", "anonim", "6698"}),
        frozenset({"kvkk_6698"}),
    ),
    "yargi": (
        frozenset({"dava", "mahkeme", "yargı", "savunma", "duruşma", "temyiz",
                   "istinaf", "bilirkişi", "2577"}),
        frozenset({"idari_yargilama_usulu_kanunu_2577"}),
    ),
    "arsiv": (
        frozenset({"arşiv", "saklama", "ayıklama", "imha", "tasnif"}),
        frozenset({"devlet_arsiv_hizmetleri_yonetmeligi"}),
    ),
    "kabahat": (
        frozenset({"kabahat", "zabıta", "gürültü", "işgal", "seyyar",
                   "dilenci", "5326"}),
        frozenset({"kabahatler_kanunu_5326"}),
    ),
    "belediye": (
        frozenset({"belediye", "zabıta", "encümen", "hemşehri", "muhtar",
                   "park", "mahalle", "5393"}),
        frozenset({"belediye_kanunu_5393"}),
    ),
    "imar": (
        frozenset({"imar", "ruhsat", "parsel", "iskân", "iskan", "inşaat",
                   "kaçak", "tadilat", "yıkım", "3194"}),
        frozenset({"imar_kanunu_3194"}),
    ),
}

# Alan mevzuatı doc_id → bağlı olduğu tema (sönümleme kontrolü için)
ALAN_MEVZUATI: Dict[str, str] = {
    doc_id: tema
    for tema, (_, doc_ids) in MEVZUAT_TEMALARI.items()
    for doc_id in doc_ids
}

# Tema aktifken alan mevzuatına uygulanan bonus; tema yokken sönümleme
TEMA_BONUSU = 1.3
ALAN_DISI_SONUMLEME = 0.7
# Bir temanın aktif sayılması için gereken farklı tetikleyici kök sayısı
TEMA_ASGARI_TETIKLEYICI = 2
# Alternatif sinyal: TEK tetikleyici kökün bu kadar farklı çekim biçimiyle
# geçmesi ("personel/personelin/personele") sözcüğün belgede merkezî
# olduğunu gösterir ve temayı tek başına aktifleştirir
TEMA_MERKEZI_BICIM = 3

# Mutlak kapsam kalibrasyonu: en iyi bölüm bile sorgudaki ayırt edici
# sözcük (IDF) kütlesinin bu oranından azını karşılıyorsa benzerlik
# orantılı düşürülür (göreli normalizasyonun zayıf eşleşmeleri 1.0'a
# şişirmesini önler; taslak ajanı benzerlik eşiği uygulayabilir).
ASGARI_KAPSAM = 0.12


class LegislationAgent:
    """
    Mevzuat eşleştirme agent'ı.

    Evrak içeriğine göre ilgili mevzuat, yönetmelik ve standart yazışma
    kurallarını önerir. Öncelik sırası:
      1. (Opsiyonel) ChromaDB semantik arama — yalnızca kuruluysa,
      2. BM25-Okapi anahtar kelime araması (birincil, bağımlılıksız yol;
         sonuçlar tür/tema koşullu ağırlıklarla yeniden sıralanır),
      3. Kural tabanlı eşleştirme (son çare).

    Korpus ve BM25 indeksi sınıf düzeyinde önbelleğe alınır; ilk kullanımda
    bir kez yüklenir, sonraki örnekler aynı indeksi paylaşır.
    """

    # Sınıf düzeyinde cache (tüm örnekler paylaşır)
    _chunks: Optional[List[Dict]] = None
    _bm25: Optional[BM25Okapi] = None

    def __init__(self) -> None:
        self.collection = None
        self._chroma_denendi = False
        logger.info("Mevzuat Agent başlatıldı (BM25 RAG).")

    # ------------------------------------------------------------------
    # Korpus yükleme ve indeksleme
    # ------------------------------------------------------------------

    @classmethod
    def _ensure_index(cls) -> None:
        """Mevzuat korpusunu ve BM25 indeksini (bir kez) belleğe yükler."""
        if cls._chunks is not None:
            return

        chunks: List[Dict] = []
        try:
            from src.config import settings

            mevzuat_dir = Path(settings.app.mevzuat_dir)
            if mevzuat_dir.is_dir():
                for path in sorted(mevzuat_dir.glob("*.txt")):
                    try:
                        chunks.extend(cls._parse_corpus_file(path))
                    except Exception as e:
                        logger.warning(f"Mevzuat dosyası okunamadı ({path.name}): {e}")
            else:
                logger.warning(f"Mevzuat dizini bulunamadı: {mevzuat_dir}")
        except Exception as e:
            logger.error(f"Mevzuat korpusu yüklenemedi: {e}")

        cls._chunks = chunks
        cls._rebuild_bm25()
        logger.info(
            f"Mevzuat korpusu yüklendi: {len({c['doc_id'] for c in chunks})} belge, "
            f"{len(chunks)} bölüm (chunk)."
        )

    @classmethod
    def _rebuild_bm25(cls) -> None:
        """Bellekteki chunk listesinden BM25 indeksini kurar."""
        if cls._chunks:
            cls._bm25 = BM25Okapi([c["tokens"] for c in cls._chunks])
        else:
            cls._bm25 = None

    @staticmethod
    def _parse_corpus_file(path: Path) -> List[Dict]:
        """
        Tek bir mevzuat dosyasını başlık bloğu + bölümlere ayırır.

        Dosya formatı:
            # Başlık: <resmî ad>
            # Kaynak: <kaynak>
            # Anahtar-Kelimeler: <virgüllü liste>
            ## <bölüm başlığı>
            <2-5 cümlelik bölüm metni>
        """
        text = path.read_text(encoding="utf-8")

        baslik = path.stem
        kaynak = "mevzuat.gov.tr (kamuya açık)"
        anahtar_kelimeler: List[str] = []
        body_lines: List[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# Başlık:"):
                baslik = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("# Kaynak:"):
                kaynak = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("# Anahtar-Kelimeler:"):
                anahtar_kelimeler = [
                    k.strip() for k in stripped.split(":", 1)[1].split(",") if k.strip()
                ]
            else:
                body_lines.append(line)

        # Bölümlere ayır (chunk = "## " ile başlayan her bölüm)
        sections: List[Tuple[str, str]] = []
        current_title = "Genel"
        current_lines: List[str] = []
        for line in body_lines:
            if line.strip().startswith("## "):
                if "\n".join(current_lines).strip():
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = line.strip()[3:].strip()
                current_lines = []
            else:
                current_lines.append(line)
        if "\n".join(current_lines).strip():
            sections.append((current_title, "\n".join(current_lines).strip()))

        keyword_text = " ".join(anahtar_kelimeler)
        chunks: List[Dict] = []
        for bolum, icerik in sections:
            chunks.append({
                "doc_id": path.stem,
                "baslik": baslik,
                "kaynak": kaynak,
                "anahtar_kelimeler": anahtar_kelimeler,
                "bolum": bolum,
                "icerik": icerik,
                # Anahtar kelimeler geri getirme kalitesi için token'lara eklenir
                "tokens": tokenize(f"{baslik} {bolum} {icerik} {keyword_text}"),
            })
        return chunks

    def index_legislation(self, documents: List[dict]) -> None:
        """
        Harici mevzuat belgelerini bellek içi korpusa ekler ve indeksi yeniler.

        Args:
            documents: Eklenecek belgeler [{baslik, metin, kaynak}, ...]
        """
        cls = type(self)
        cls._ensure_index()
        chunks = cls._chunks if cls._chunks is not None else []

        for i, doc in enumerate(documents):
            metin = doc.get("metin", "") or ""
            baslik = doc.get("baslik", f"Mevzuat #{i + 1}")
            anahtar = doc.get("anahtar_kelimeler", []) or []
            chunks.append({
                "doc_id": f"harici_{len(chunks)}_{i}",
                "baslik": baslik,
                "kaynak": doc.get("kaynak", ""),
                "anahtar_kelimeler": anahtar,
                "bolum": "Genel",
                "icerik": metin,
                "tokens": tokenize(f"{baslik} {metin} {' '.join(anahtar)}"),
            })

        cls._chunks = chunks
        cls._rebuild_bm25()
        logger.info(f"{len(documents)} mevzuat belgesi bellek içi korpusa eklendi.")

    # ------------------------------------------------------------------
    # Ana çalışma akışı
    # ------------------------------------------------------------------

    def run(self, state: "AgentState") -> "AgentState":
        """Evrak içeriğine göre ilgili mevzuat önerilerini üretir."""
        evrak_turu = state.classification.get("tur", "")
        konu = ""
        if isinstance(state.extracted_info, dict):
            konu = state.extracted_info.get("konu") or ""
        query_text = f"{konu}\n{state.raw_text[:SORGU_METIN_LIMITI]}".strip()

        self._ensure_index()

        matches: List[dict] = []

        # 1) Opsiyonel semantik arama — yalnızca chromadb kuruluysa denenir
        if importlib.util.find_spec("chromadb") is not None:
            matches = self._search_vector_db(query_text)

        # 2) Birincil yol: BM25 anahtar kelime araması (tür-koşullu sıralama)
        if not matches:
            matches = self._bm25_search(query_text, evrak_turu)

        # 3) Son çare: kural tabanlı eşleştirme
        if not matches:
            matches = self._rule_based_match(evrak_turu)

        # Şartname: türü düzenleyen usul mevzuatı (yazışma kuralları /
        # dilekçe hakkı) önerilerin başında yer alır
        matches = self._ensure_usul_mevzuati(matches, evrak_turu)

        state.legislation_matches = matches[:5]
        logger.info(f"Mevzuat eşleştirmesi: {len(state.legislation_matches)} sonuç")
        return state

    # ------------------------------------------------------------------
    # BM25 arama
    # ------------------------------------------------------------------

    def _bm25_search(self, query_text: str, evrak_turu: str = "", top_n: int = 5) -> List[dict]:
        """
        BM25 ile en ilgili chunk'ları bulur; skorlar tür/tema koşullu
        ağırlıklarla yeniden sıralanır ve mevzuat başına tek (en iyi)
        sonuç döndürülür. Benzerlik değeri, göreli skorun mutlak kapsam
        kalitesiyle (sorgu IDF kütlesinin karşılanma oranı) çarpımıdır;
        böylece zayıf eşleşmeler 1.0'a şişmez ve düşük benzerlikte kalır.
        """
        cls = type(self)
        chunks = cls._chunks or []
        if cls._bm25 is None or not chunks:
            return []

        query_tokens = tokenize(query_text)
        if not query_tokens:
            return []

        raw_scores = cls._bm25.get_scores(query_tokens)
        aktif_temalar = self._aktif_temalar(query_tokens)
        tur_agirliklari = TUR_MEVZUAT_AGIRLIKLARI.get(evrak_turu, {})

        # Tür/tema koşullu ağırlıklandırılmış skorlar
        agirliklar: Dict[str, float] = {}
        scores: List[float] = []
        for i, raw in enumerate(raw_scores):
            doc_id = chunks[i]["doc_id"]
            if doc_id not in agirliklar:
                agirliklar[doc_id] = self._doc_agirligi(
                    doc_id, tur_agirliklari, aktif_temalar
                )
            scores.append(raw * agirliklar[doc_id])

        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        if not ranked or scores[ranked[0]] <= 0:
            return []
        max_score = scores[ranked[0]]

        # Mevzuat (doc_id) başına en iyi chunk
        best_per_doc: Dict[str, int] = {}
        for i in ranked:
            if scores[i] <= 0:
                break
            doc_id = chunks[i]["doc_id"]
            if doc_id not in best_per_doc:
                best_per_doc[doc_id] = i
                if len(best_per_doc) >= top_n:
                    break

        matches: List[dict] = []
        for i in best_per_doc.values():
            chunk = chunks[i]
            benzerlik = (scores[i] / max_score) * self._kapsam_kalitesi(
                query_tokens, chunk
            )
            matches.append({
                "baslik": chunk["baslik"],
                "icerik_ozeti": self._chunk_ozeti(chunk),
                "benzerlik": round(benzerlik, 3),
                "kaynak": chunk["kaynak"],
                "anahtar_kelimeler": chunk["anahtar_kelimeler"],
            })
        # Kapsam kalibrasyonu sıralamayı değiştirebilir; nihai benzerliğe
        # göre sırala (liste tekdüze azalan benzerlikle sunulur)
        matches.sort(key=lambda m: m["benzerlik"], reverse=True)
        return matches

    @staticmethod
    def _aktif_temalar(query_tokens: List[str]) -> set:
        """
        Sorguda söz dağarcığı bulunan temaları döndürür.

        Bir tema iki koşuldan biriyle aktif sayılır (önek eşleşmesi:
        "fatura" → "faturamın"):
          1. EN AZ İKİ FARKLI tetikleyici kök geçiyorsa, veya
          2. TEK tetikleyici kök EN AZ ÜÇ farklı çekim biçimiyle geçiyorsa
             (sözcük belgede merkezî demektir).
        Tek sözcüklük tekil çakışmalar tesadüfi kabul edilir.
        """
        uniq = set(query_tokens)
        aktif = set()
        for tema, (tetikleyiciler, _) in MEVZUAT_TEMALARI.items():
            eslesen_kok = 0
            en_cok_bicim = 0
            for kok in tetikleyiciler:
                bicim_sayisi = sum(1 for token in uniq if token.startswith(kok))
                if bicim_sayisi:
                    eslesen_kok += 1
                    en_cok_bicim = max(en_cok_bicim, bicim_sayisi)
            if eslesen_kok >= TEMA_ASGARI_TETIKLEYICI or en_cok_bicim >= TEMA_MERKEZI_BICIM:
                aktif.add(tema)
        return aktif

    @staticmethod
    def _doc_agirligi(
        doc_id: str, tur_agirliklari: Dict[str, float], aktif_temalar: set
    ) -> float:
        """
        Bir mevzuat belgesinin tür/tema koşullu skor çarpanını hesaplar.

        Tür önceliği ile tema bonusu/sönümlemesi çarpılarak birleştirilir:
        alan mevzuatı, teması sorguda aktifse TEMA_BONUSU kazanır; aktif
        değilse ALAN_DISI_SONUMLEME ile geriye itilir (tesadüfi sözcük
        çakışmasının üst sıraya çıkmasını önler).
        """
        agirlik = tur_agirliklari.get(doc_id, 1.0)
        tema = ALAN_MEVZUATI.get(doc_id)
        if tema is not None:
            agirlik *= TEMA_BONUSU if tema in aktif_temalar else ALAN_DISI_SONUMLEME
        return agirlik

    @classmethod
    def _kapsam_kalitesi(cls, query_tokens: List[str], chunk: Dict) -> float:
        """
        Bölümün sorguyu mutlak olarak ne ölçüde karşıladığını [0-1] döndürür.

        Ölçü: bölümde geçen sorgu token'larının IDF kütlesinin, sorgunun
        korpus dağarcığındaki toplam IDF kütlesine oranı (kapsam). Kapsam
        ASGARI_KAPSAM'ın altındaysa oran orantılı cezalandırılır; üstünde
        tam puan verilir (göreli sıralamayı bozmadan mutlak kalibrasyon).
        """
        if cls._bm25 is None:
            return 1.0
        idf = cls._bm25.idf
        uniq = set(query_tokens)
        toplam = sum(idf.get(t, 0.0) for t in uniq)
        if toplam <= 0:
            return 0.0
        chunk_tokens = set(chunk["tokens"])
        kapsam = sum(idf.get(t, 0.0) for t in uniq if t in chunk_tokens) / toplam
        return min(1.0, kapsam / ASGARI_KAPSAM)

    @staticmethod
    def _chunk_ozeti(chunk: Dict, limit: int = OZET_LIMITI) -> str:
        """Chunk'ın bölüm başlığı + içeriğinden ~300 karakterlik özet üretir."""
        metin = re.sub(r"\s+", " ", f"{chunk['bolum']}: {chunk['icerik']}").strip()
        if len(metin) <= limit:
            return metin
        kesik = metin[:limit].rsplit(" ", 1)[0]
        return kesik + "..."

    # ------------------------------------------------------------------
    # Tür usul mevzuatı garantisi (şartname: standart yazışma kuralları)
    # ------------------------------------------------------------------

    def _ensure_usul_mevzuati(self, matches: List[dict], evrak_turu: str) -> List[dict]:
        """
        Evrak türünü doğrudan düzenleyen usul mevzuatını önerilerin başına
        alır: yazışma türlerinde Resmî Yazışma Yönetmeliği, dilekçede 3071
        sayılı Dilekçe Hakkı Kanunu. Bu mevzuatın ilgililiği sözcük
        çakışmasından değil türün kendisinden geldiği için, listede varsa
        başa taşınır, yoksa korpustan eklenir; benzerliği en az 0.8 olarak
        raporlanır.
        """
        doc_id = TUR_USUL_MEVZUATI.get(evrak_turu)
        if not doc_id:
            return matches

        cls = type(self)
        chunk = None
        for c in cls._chunks or []:
            if c["doc_id"] == doc_id:
                chunk = c
                break
        if chunk is None:
            return matches

        # Liste başına alınan usul mevzuatının benzerliği, mevcut en
        # yüksek benzerlikten (ve 0.8 tabanından) düşük raporlanmaz
        en_yuksek = matches[0]["benzerlik"] if matches else 0.8

        # Listede varsa başa taşı
        for i, m in enumerate(matches):
            if m.get("baslik") == chunk["baslik"]:
                tasinan = matches.pop(i)
                tasinan["benzerlik"] = round(
                    max(float(tasinan.get("benzerlik") or 0.0), float(en_yuksek), 0.8), 3
                )
                tasinan["eklenme_nedeni"] = "tur_usul_mevzuati"
                return [tasinan] + matches
        usul_onerisi = {
            "baslik": chunk["baslik"],
            "icerik_ozeti": self._chunk_ozeti(chunk),
            "benzerlik": round(max(float(en_yuksek), 0.8), 3),
            "kaynak": chunk["kaynak"],
            "anahtar_kelimeler": chunk["anahtar_kelimeler"],
            "eklenme_nedeni": "tur_usul_mevzuati",
        }
        return [usul_onerisi] + matches

    # ------------------------------------------------------------------
    # Opsiyonel ChromaDB semantik arama
    # ------------------------------------------------------------------

    def _init_vector_db(self) -> None:
        """ChromaDB koleksiyonunu (kuruluysa) bir kez başlatmayı dener."""
        if self._chroma_denendi:
            return
        self._chroma_denendi = True
        try:
            import chromadb  # lazy import — yalnızca kuruluysa
            from src.config import settings

            client = chromadb.PersistentClient(path=settings.chroma.persist_dir)
            self.collection = client.get_or_create_collection(
                name=settings.chroma.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB koleksiyonu yüklendi: {self.collection.count()} kayıt")
        except Exception as e:
            logger.warning(f"ChromaDB başlatılamadı, BM25 kullanılacak: {e}")
            self.collection = None

    def _search_vector_db(self, query_text: str) -> List[dict]:
        """ChromaDB'de semantik arama yapar; her hata durumunda [] döner (BM25'e düşülür)."""
        try:
            self._init_vector_db()
            if self.collection is None or self.collection.count() == 0:
                return []

            results = self.collection.query(
                query_texts=[query_text[:1000]],
                n_results=5,
            )

            matches: List[dict] = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = (
                        results["distances"][0][i] if results.get("distances") else 1.0
                    )
                    matches.append({
                        "baslik": meta.get("baslik", f"Mevzuat #{i + 1}"),
                        "icerik_ozeti": doc[:OZET_LIMITI],
                        "benzerlik": round(max(0.0, 1 - distance), 3),
                        "kaynak": meta.get("kaynak", ""),
                        "anahtar_kelimeler": [],
                    })
            return matches
        except Exception as e:
            logger.warning(f"Semantik arama başarısız, BM25'e düşülüyor: {e}")
            return []

    # ------------------------------------------------------------------
    # Kural tabanlı eşleştirme (son çare)
    # ------------------------------------------------------------------

    def _rule_based_match(self, evrak_turu: str) -> List[dict]:
        """Korpus/BM25 kullanılamadığında evrak türüne göre temel mevzuat önerir."""
        base_regulations = [
            {
                "baslik": "Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik",
                "aciklama": "Tüm resmî yazışmalarda uyulması gereken format ve usul kuralları",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["ust_yazi", "cevap_yazisi", "bilgilendirme", "genelge"],
            },
            {
                "baslik": "3071 Sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun",
                "aciklama": "Dilekçede zorunlu bilgiler ve 30 gün içinde cevap verme yükümlülüğü",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["dilekce"],
            },
            {
                "baslik": "4982 Sayılı Bilgi Edinme Hakkı Kanunu",
                "aciklama": "Bilgi edinme başvurusu usulü ve 15 iş günlük cevap süresi",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["dilekce", "bilgilendirme", "cevap_yazisi"],
            },
            {
                "baslik": "Devlet Arşiv Hizmetleri Hakkında Yönetmelik",
                "aciklama": "Evrakın arşivlenmesi, saklama süreleri, ayıklama ve imha usulleri",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["ust_yazi", "tutanak", "rapor"],
            },
            {
                "baslik": "5070 Sayılı Elektronik İmza Kanunu",
                "aciklama": "Güvenli elektronik imzanın hukuki geçerliliği ve elektronik belge",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["onayli_belge", "ust_yazi", "cevap_yazisi"],
            },
        ]

        matches: List[dict] = []
        for reg in base_regulations:
            if evrak_turu in reg["ilgili_turler"] or not evrak_turu:
                matches.append({
                    "baslik": reg["baslik"],
                    "icerik_ozeti": reg["aciklama"],
                    "benzerlik": 0.8 if evrak_turu in reg["ilgili_turler"] else 0.3,
                    "kaynak": reg["kaynak"],
                    "anahtar_kelimeler": [],
                })

        return sorted(matches, key=lambda x: x["benzerlik"], reverse=True)
