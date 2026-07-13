"""
Mevzuat Eşleştirme Agent — hibrit (BM25 ∪ opsiyonel semantik) RAG ile
madde-referanslı ve gerekçeli mevzuat önerisi.

data/raw/mevzuat_metinleri/ altındaki mevzuat özet dosyalarını bölüm
bazında parçalara (chunk) ayırır, her bölümün atıf yaptığı madde
numaralarını çıkarır ve saf Python BM25-Okapi indeksiyle bellekte arar.
Benzerlik değerleri MUTLAK ölçektedir (sorgu IDF kütlesinden türetilen
doygunluk noktasına oran); göreli normalizasyonun zayıf eşleşmeleri 1.0'a
şişirmesi bilinçli olarak terk edilmiştir ve en iyi eşleşme bile zayıfsa
sonuçlar "zayif_esleme" işaretiyle döner (benzerlik dürüstlüğü).

Opsiyonel katmanlar (sentence-transformers kuruluysa ve ayarla açılmışsa):
turkish-e5-large yoğun arama adayları BM25 ile puan birleşimine girer,
bge-reranker-v2-m3 aday havuzunu yeniden sıralar. En iyi eşleşmenin
benzerliği eşiğin altında kalırsa evrak türünün usul söz dağarcığıyla
sorgu bir kez genişletilip arama yinelenir (düzeltici/corrective RAG
döngüsü — bkz. Singh vd. 2025, arXiv:2501.09136; Li vd. 2025,
arXiv:2507.09477). Hiçbir opsiyonel katman yokken sistem tamamen kural
tabanlı + BM25 ile offline çalışır; hiçbir yol sonuç üretemezse evrak
türüne göre kural tabanlı eşleştirmeye düşülür.

Her öneri şu alanları taşır: {mevzuat_adi, madde_no, gerekce, benzerlik
(skor), doc_id, bolum, icerik_ozeti, kaynak} — gerekçe ve madde alanları
halüsinasyonsuz, tamamen korpus içeriğinden ve eşleşme sinyallerinden
türetilir.

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
from src.utils.semantik_arama import (
    SemantikArama,
    YenidenSiralayici,
    puan_birlestir,
    rrf_birlestir,
)
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

# Bölüm metinlerindeki madde atıflarını yakalayan desen. Korpusta gözlenen
# biçimler: "(m. 14)", "(m. 22-23)" (aralık) ve "m. 4'te" (parantezsiz,
# kesme ekli). Kanun numarası atıfları ("3071 sayılı") madde DEĞİLDİR ve
# "m." öneki zorunlu olduğu için yakalanmaz; madde numaraları korpusta en
# fazla üç hanelidir.
MADDE_DESENI = re.compile(r"\bm\.\s*(\d{1,3})(?:-(\d{1,3}))?")

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

# ----------------------------------------------------------------------
# Mutlak benzerlik kalibrasyonu (benzerlik dürüstlüğü)
#
# Göreli normalizasyon (skor / en_iyi_skor) en iyi eşleşmeyi eşleşme ne
# kadar zayıf olursa olsun 1.0'a şişirir; taslak ajanı bu değeri yasal
# dayanak atfı için eşikle süzdüğünden şişirme yanlış mevzuat alıntısına
# dönüşebilir (etik risk). Benzerlik bu yüzden MUTLAK bir doygunluk
# noktasına oranlanır ve 1.0'a kırpılır:
#
#   benzerlik = min(1, agirlikli_skor / (DOYGUNLUK_KATSAYISI * toplam_idf))
#
# toplam_idf, sorgunun korpus dağarcığındaki ayırt edici sözcük (IDF)
# kütlesidir. BM25 teorisinde ortalama uzunluktaki bir bölümde TEK geçiş
# (tf=1) tam olarak idf katkısı verir; katkı tf arttıkça (k1+1)=2.5·idf
# doygunluğuna yaklaşır (tf=2 → 1.43·idf, tf=3 → 1.67·idf). Katsayı 1.5,
# "tam benzerlik" tanımını sorgu sözcüklerinin bölümde MERKEZÎ (tekrarlı,
# tf≈2-3) kullanılmasına bağlar: her sözcüğe yalnızca bir kez değinen bir
# bölüm ≤ ~0.67, sorgunun küçük bir kısmına değinen bölüm ise orantılı
# olarak düşük benzerlik alır. Ölçek korpus istatistiğine (IDF) dayanır,
# belge/veri kümesine özel ezber içermez.
DOYGUNLUK_KATSAYISI = 1.5

# En iyi eşleşme bile bu mutlak eşiğin altındaysa sonuç listesi "zayıf
# eşleşme" işaretiyle döner: korpusta evraka gerçekten uyan hüküm yok
# demektir ve tüketiciler (arayüz/raporlama) bunu şeffafça gösterebilir.
ZAYIF_ESLESME_ESIGI = 0.5

# ----------------------------------------------------------------------
# KVKK veri-tespit sinyali köprüsü
#
# 6698 sayılı KVKK, "kişisel/kvkk/rıza" sözcükleri metinde GEÇMESE dahi
# belge gerçek kişiye ait kişisel veri (doğrulanmış T.C. kimlik numarası
# veya IBAN) içeriyorsa uygulanır. Tema aktifleşmesi tetikleyici sözcüklere
# bağlı olduğundan bu tür belgelerde (KVKK-yoğun ama sözcüksüz evrak) 6698
# kaçırılıyordu. İnfo-çıkarım ajanının veri-tespit sinyali (extracted_info),
# bir usul yükümlülüğü gibi (bkz. _ensure_usul_mevzuati) doğrudan mevzuat
# önerisine bağlanır. Enjekte edilen öneri metinsel eşleşme İDDİA ETMEZ:
# benzerliği taslak atıf eşiğinin (MEVZUAT_ATIF_ESIGI = 0.6) ALTINDA
# tutulur — öneri/uyarı olarak görünür ama taslak alıntısını zorlamaz;
# eklenme_nedeni ve gerekçe sinyal kökenini şeffafça bildirir.
KVKK_6698_DOC_ID = "kvkk_6698"
KVKK_SINYAL_BENZERLIK = 0.55

# ----------------------------------------------------------------------
# Düzeltici (corrective) arama döngüsü ve hibrit birleşim sabitleri
# ----------------------------------------------------------------------

# Düzeltici döngü tetiği, zayıf-eşleşme İŞARETİNDEN (0.5) bilinçli olarak
# ayrıdır ve daha aşağıdadır: işaret şeffaflık içindir, tetik ise yalnızca
# sorgu söz dağarcığı korpusla GERÇEKTEN örtüşmediğinde (ör. korpus dışı
# terminoloji, bozuk OCR çıktısı) devreye giren güvenlik ağıdır. Eşik
# geliştirme seti gözlemiyle kalibre edilmiştir (held-out kullanılmadı):
# 35 evraklık ilk geliştirme setinde (52'ye genişletme öncesi kalibrasyon)
# ilk-en-iyi benzerlik min 0.107 / medyan 0.245
# ölçülmüş; tetik 0.5'te döngü 33/35 evrakta ateşlenip usul terimleriyle
# alan mevzuatını ilk üçten itebildiğinden isabet@3 0.943→0.914 düşmüş,
# 0.15'te ise isabet 0.943'te kalarak döngü yalnızca 2 sınır evrakta
# çalışmıştır. Bu yüzden 0.15: iyi eşleşen evraklara dokunmaz, söz
# dağarcığı uyuşmazlığında devreye girer (birim testle doğrulanır).
DUZELTME_ESIGI = 0.15

# Evrak türü → sorgu genişletmede kullanılan usul söz dağarcığı. Terimler
# belge içeriğine değil türün hukuki bağlamına aittir; düzeltme döngüsü
# sorgunun mevzuat korpusu dağarcığıyla hizalanmasını sağlar.
TUR_SORGU_GENISLETME: Dict[str, List[str]] = {
    "dilekce": ["dilekçe", "başvuru", "talep", "şikâyet", "cevap", "süre",
                "imza", "adres", "yetkili", "makam"],
    "cevap_yazisi": ["resmî", "yazışma", "cevap", "başvuru", "ilgi", "sayı",
                     "usul", "süre"],
    "ust_yazi": ["resmî", "yazışma", "usul", "sayı", "konu", "imza",
                 "dağıtım", "belge"],
    "bilgilendirme": ["resmî", "yazışma", "duyuru", "bilgilendirme", "usul",
                      "belge"],
    "genelge": ["resmî", "yazışma", "genelge", "talimat", "uygulama", "usul"],
    "tutanak": ["tutanak", "tespit", "imza", "katılımcı", "arşiv", "saklama",
                "belge"],
    "rapor": ["rapor", "değerlendirme", "bulgu", "arşiv", "saklama",
              "dosyalama"],
    "onayli_belge": ["elektronik", "imza", "onay", "güvenli", "sertifika",
                     "belge"],
}

# Hibrit birleşimde BM25 tarafının ağırlığı (kalan semantik tarafa gider).
# BM25 birincildir: çekirdek yol, mevzuat dilindeki birebir terim
# çakışmasında güçlüdür; semantik katman eş anlamlı ifadeleri tamamlar.
# Birleşim mutlak ölçekte yapılır: BM25 tarafı doygunluk-oranlı benzerlik,
# semantik taraf kosinüs benzerliği (ikisi de [0-1]).
HIBRIT_BM25_AGIRLIK = 0.6

# Hibrit SIRALAMA: BM25 + opsiyonel dense listeleri rank-tabanlı Reciprocal
# Rank Fusion (RRF, Cormack vd. 2009) ile birleştirilir. RRF ölçek-bağımsızdır
# ve farklı dağılımlı (BM25-mutlak vs. dense-kosinüs) skorları doğrudan toplamanın
# (dışbükey puan_birlestir) ölçek uyumsuzluğunu giderir. Rapor edilen `benzerlik`
# alanı DAİMA mutlak BM25 doygunluk ölçeğinde kalır (etik/atıf/zayıf-eşleşme
# doğrulaması bununla yapılır); RRF yalnızca sırayı belirler. Kapatılırsa eski
# dışbükey birleşime düşülür. Salt-BM25 (offline çekirdek) yolunda RRF/dışbükey
# fark etmez — davranış birebir korunur.
HIBRIT_RRF_AKTIF = True

# Opsiyonel katmanlara (semantik aday havuzu, rerank) verilen aday sayısı
ADAY_HAVUZU = 10

# Gerekçede listelenen en ayırt edici (yüksek IDF) ortak terim sayısı
GEREKCE_TERIM_SAYISI = 3


def madde_referanslari(metin: str) -> List[str]:
    """
    Bölüm metnindeki madde atıflarını sıra korunarak (tekrarsız) çıkarır.

    "(m. 14)" → "14"; "(m. 22-23)" aralığı → "22-23"; "m. 4'te" → "4".
    Madde atfı olmayan metin için boş liste döner (bilgi notları gibi
    korpus dosyalarında bu normal akıştır).
    """
    gorulen: List[str] = []
    for esleme in MADDE_DESENI.finditer(metin):
        no = esleme.group(1)
        if esleme.group(2):
            no = f"{no}-{esleme.group(2)}"
        if no not in gorulen:
            gorulen.append(no)
    return gorulen


def madde_etiketi(madde_no: List[str]) -> str:
    """Madde listesini insan-okur etikete çevirir: ["4","22-23"] → "m. 4, m. 22-23"."""
    return ", ".join(f"m. {n}" for n in madde_no)


class LegislationAgent:
    """
    Mevzuat eşleştirme agent'ı.

    Evrak içeriğine göre ilgili mevzuat, yönetmelik ve standart yazışma
    kurallarını madde referansı ve gerekçesiyle önerir. Akış:
      1. BM25-Okapi anahtar kelime araması (çekirdek, bağımlılıksız yol;
         sonuçlar tür/tema koşullu ağırlıklarla yeniden sıralanır, benzerlik
         mutlak doygunluk ölçeğindedir),
      2. (Opsiyonel) turkish-e5-large yoğun arama adayları BM25 ile puan
         birleşimine girer; (opsiyonel) bge-reranker-v2-m3 adayları
         yeniden sıralar — ikisi de yoksa salt BM25 davranışı birebir korunur,
      3. En iyi benzerlik DUZELTME_ESIGI altındaysa tür söz dağarcığıyla
         sorgu genişletilip arama BİR KEZ yinelenir (corrective RAG),
      4. (Opsiyonel) ChromaDB semantik arama — yalnızca BM25 indeksi
         kurulamadıysa yedek yol olarak denenir,
      5. Kural tabanlı eşleştirme (son çare).

    Korpus ve BM25 indeksi sınıf düzeyinde önbelleğe alınır; ilk kullanımda
    bir kez yüklenir, sonraki örnekler aynı indeksi paylaşır.
    """

    # Sınıf düzeyinde cache (tüm örnekler paylaşır)
    _chunks: Optional[List[Dict]] = None
    _bm25: Optional[BM25Okapi] = None
    # Opsiyonel katman örnekleri: None = henüz denenmedi, False = kullanılamaz
    _semantik: object = None
    _rerank: object = None

    def __init__(self) -> None:
        self.collection = None
        self._chroma_denendi = False
        logger.info("Mevzuat Agent başlatıldı (hibrit BM25 RAG).")

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
        # Chunk listesi değişti: semantik gömme indeksi bayatladı, ilk
        # kullanımda yeniden kurulsun
        cls._semantik = None

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

        Her bölüm bir chunk olur; bölümün atıf yaptığı madde numaraları
        (madde_referanslari) chunk üstverisine işlenir — böylece öneriler
        mevzuat adıyla birlikte madde numarası taşıyabilir.
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
                "madde_no": madde_referanslari(icerik),
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
                "madde_no": madde_referanslari(metin),
                "tokens": tokenize(f"{baslik} {metin} {' '.join(anahtar)}"),
            })

        cls._chunks = chunks
        cls._rebuild_bm25()
        logger.info(f"{len(documents)} mevzuat belgesi bellek içi korpusa eklendi.")

    # ------------------------------------------------------------------
    # Opsiyonel katman erişimi (zarif düşüşlü)
    # ------------------------------------------------------------------

    def _ensure_semantik(self) -> Optional[SemantikArama]:
        """Semantik arama katmanını (bir kez) kurmayı dener; yoksa None."""
        cls = type(self)
        if cls._semantik is False:
            return None
        if cls._semantik is None:
            sa = SemantikArama()
            chunks = cls._chunks or []
            metinler = [
                f"{c['baslik']} {c['bolum']} {c['icerik']}" for c in chunks
            ]
            if not sa.aktif() or not sa.indeksle(metinler):
                cls._semantik = False
                return None
            cls._semantik = sa
        return cls._semantik  # type: ignore[return-value]

    def _ensure_rerank(self) -> Optional[YenidenSiralayici]:
        """Yeniden sıralama katmanını (bir kez) kurmayı dener; yoksa None."""
        cls = type(self)
        if cls._rerank is False:
            return None
        if cls._rerank is None:
            rr = YenidenSiralayici()
            if not rr.aktif():
                cls._rerank = False
                return None
            cls._rerank = rr
        return cls._rerank  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Ana çalışma akışı
    # ------------------------------------------------------------------

    def run(self, state: "AgentState") -> "AgentState":
        """Evrak içeriğine göre ilgili mevzuat önerilerini üretir."""
        evrak_turu = state.classification.get("tur", "")
        konu = ""
        ei = state.extracted_info if isinstance(state.extracted_info, dict) else {}
        konu = ei.get("konu") or ""
        query_text = f"{konu}\n{state.raw_text[:SORGU_METIN_LIMITI]}".strip()

        # KVKK veri-tespit sinyali: belge doğrulanmış T.C. kimlik numarası
        # ya da IBAN içeriyorsa (gerçek kişiye ait kişisel veri), 6698 sayılı
        # KVKK sözcüksel eşleşmeden bağımsız olarak ilgilidir (bkz.
        # _ensure_kvkk_mevzuati). TCKN checksum'lı doğrulanmıştır; kurumlar
        # TCKN taşımaz, bu yüzden yanlış-pozitif riski düşüktür.
        kvkk_veri_sinyali = bool(ei.get("tc_kimlik")) or bool(ei.get("iban"))

        self._ensure_index()

        # 1) Birincil yol: hibrit arama (BM25 + opsiyonel katmanlar)
        matches, yontem = self._hibrit_ara(query_text, evrak_turu)

        # 2) Düzeltici döngü: en iyi benzerlik eşiğin altındaysa (zayıf
        #    eşleşme) sorguyu türün usul söz dağarcığıyla genişletip BİR KEZ
        #    yeniden ara; yalnızca en iyi benzerlik iyileşirse benimse
        ilk_benzerlik = matches[0]["benzerlik"] if matches else 0.0
        duzeltme = {
            "uygulandi": False,
            "esik": DUZELTME_ESIGI,
            "ilk_en_iyi_benzerlik": round(ilk_benzerlik, 3),
            "eklenen_terimler": [],
        }
        genisletme = TUR_SORGU_GENISLETME.get(evrak_turu, [])
        if ilk_benzerlik < DUZELTME_ESIGI and genisletme:
            genis_sorgu = f"{query_text} {' '.join(genisletme)}"
            yeni_matches, yeni_yontem = self._hibrit_ara(
                genis_sorgu, evrak_turu, duzeltilmis=True
            )
            yeni_benzerlik = yeni_matches[0]["benzerlik"] if yeni_matches else 0.0
            if yeni_benzerlik > ilk_benzerlik:
                matches, yontem = yeni_matches, yeni_yontem
                duzeltme["uygulandi"] = True
                duzeltme["eklenen_terimler"] = list(genisletme)
                duzeltme["son_en_iyi_benzerlik"] = round(yeni_benzerlik, 3)
                logger.info(
                    "Düzeltici döngü uygulandı: benzerlik "
                    f"{ilk_benzerlik:.3f} → {yeni_benzerlik:.3f}"
                )

        # 3) Yedek yol: BM25 indeksi kurulamadıysa ChromaDB (kuruluysa)
        if not matches and importlib.util.find_spec("chromadb") is not None:
            matches = self._search_vector_db(query_text)
            if matches:
                yontem = "chromadb"

        # 4) Son çare: kural tabanlı eşleştirme
        if not matches:
            matches = self._rule_based_match(evrak_turu)
            if matches:
                yontem = "kural_tabanli"

        # Şartname: türü düzenleyen usul mevzuatı (yazışma kuralları /
        # dilekçe hakkı) önerilerin başında yer alır
        matches = self._ensure_usul_mevzuati(matches, evrak_turu)

        # KVKK köprüsü: kişisel veri saptandıysa 6698'i öneri listesine
        # (ilk üçe) al — usul mevzuatı ve en iyi metinsel eşleşme korunur
        matches = self._ensure_kvkk_mevzuati(matches, kvkk_veri_sinyali)

        state.legislation_matches = matches[:5]
        state.legislation_meta = {
            "yontem": yontem,
            "duzeltme_dongusu": duzeltme,
            "kvkk_veri_sinyali": kvkk_veri_sinyali,
        }
        logger.info(
            f"Mevzuat eşleştirmesi: {len(state.legislation_matches)} sonuç "
            f"(yöntem: {yontem})"
        )
        return state

    # ------------------------------------------------------------------
    # Hibrit arama (BM25 çekirdek + opsiyonel semantik/rerank)
    # ------------------------------------------------------------------

    def _hibrit_ara(
        self,
        query_text: str,
        evrak_turu: str = "",
        top_n: int = 5,
        duzeltilmis: bool = False,
    ) -> Tuple[List[dict], str]:
        """
        BM25 ve (varsa) semantik adayları puan birleşimiyle harmanlar,
        (varsa) yeniden sıralar; mevzuat başına tek (en iyi) sonuç döndürür.

        Benzerlik MUTLAK ölçektedir: BM25 tarafında ağırlıklı skor, sorgunun
        IDF kütlesinden türetilen doygunluk noktasına oranlanıp 1.0'a
        kırpılır (bkz. DOYGUNLUK_KATSAYISI); semantik taraf kosinüs
        benzerliği katar. En iyi eşleşme dahi göreli sıradan bağımsız
        değerlendirildiği için alakasız sorgular düşük benzerlikte kalır;
        en iyi benzerlik ZAYIF_ESLESME_ESIGI altındaysa tüm sonuçlar
        "zayif_esleme": True işaretiyle döner. Opsiyonel katmanların ikisi
        de yokken davranış salt BM25 aramasıyla birebir aynıdır.

        Returns:
            (öneri listesi, kullanılan yöntem etiketi)
        """
        cls = type(self)
        chunks = cls._chunks or []
        if cls._bm25 is None or not chunks:
            return [], "yok"

        query_tokens = tokenize(query_text)
        if not query_tokens:
            return [], "yok"

        # Mutlak doygunluk noktası: sorgunun korpus dağarcığındaki IDF kütlesi
        idf = cls._bm25.idf
        toplam_idf = sum(idf.get(t, 0.0) for t in set(query_tokens))
        if toplam_idf <= 0:
            return [], "yok"
        doygunluk = DOYGUNLUK_KATSAYISI * toplam_idf

        raw_scores = cls._bm25.get_scores(query_tokens)
        aktif_temalar = self._aktif_temalar(query_tokens)
        tur_agirliklari = TUR_MEVZUAT_AGIRLIKLARI.get(evrak_turu, {})

        # Tür/tema koşullu ağırlıklandırılmış, doygunluk-oranlı MUTLAK
        # BM25 benzerlikleri
        agirliklar: Dict[str, float] = {}
        bm25_benzerlik: Dict[int, float] = {}
        for i, raw in enumerate(raw_scores):
            if raw <= 0:
                continue
            doc_id = chunks[i]["doc_id"]
            if doc_id not in agirliklar:
                agirliklar[doc_id] = self._doc_agirligi(
                    doc_id, tur_agirliklari, aktif_temalar
                )
            bm25_benzerlik[i] = min(1.0, raw * agirliklar[doc_id] / doygunluk)

        # Opsiyonel yoğun (dense) aday havuzu → mutlak ölçekte puan birleşimi
        yontem = "bm25"
        dense_benzerlik: Dict[int, float] = {}
        semantik = self._ensure_semantik()
        if semantik is not None:
            adaylar = semantik.ara(query_text, top_n=ADAY_HAVUZU)
            if adaylar:
                dense_benzerlik = {i: max(0.0, s) for i, s in adaylar}
                yontem = "bm25+semantik"

        # Sıralama puanı: BM25 (+ opsiyonel dense) rank-tabanlı RRF ile
        # ölçek-bağımsız birleştirilir. Salt-BM25 (dense kapalı) yolunda
        # davranış BİREBİR korunur. Mutlak BM25 benzerliği (bm25_benzerlik)
        # aşağıda `benzerlik` alanı olarak ayrıca korunur.
        if dense_benzerlik and HIBRIT_RRF_AKTIF:
            siralama_puani = rrf_birlestir([bm25_benzerlik, dense_benzerlik])
        elif dense_benzerlik:
            siralama_puani = puan_birlestir(
                bm25_benzerlik, dense_benzerlik, HIBRIT_BM25_AGIRLIK
            )
        else:
            siralama_puani = dict(bm25_benzerlik)  # yalnız BM25 — offline çekirdek
        if not siralama_puani:
            return [], yontem

        # Opsiyonel yeniden sıralama: en iyi ADAY_HAVUZU aday çapraz kodlayıcıyla
        # yeniden SIRALANIR (skoru yalnızca sıralama için kullanılır)
        rerank = self._ensure_rerank()
        if rerank is not None:
            aday_idx = [
                i for i, _ in sorted(
                    siralama_puani.items(), key=lambda kv: kv[1], reverse=True
                )[:ADAY_HAVUZU]
            ]
            rerank_puanlari = rerank.sirala(
                query_text, [chunks[i]["icerik"] for i in aday_idx]
            )
            if rerank_puanlari:
                siralama_puani = dict(zip(aday_idx, rerank_puanlari))
                yontem += "+rerank"

        # Mevzuat (doc_id) başına en iyi chunk: SIRALAMA puanına göre seçilir,
        # ancak rapor edilen benzerlik MUTLAK BM25 doygunluk ölçeğindedir
        # (etik/atıf/zayıf-eşleşme dürüstlüğü — RRF/rerank yalnızca sırayı belirler).
        ranked = sorted(siralama_puani.items(), key=lambda kv: kv[1], reverse=True)
        best_per_doc: Dict[str, Tuple[int, float]] = {}
        for i, s_puan in ranked:
            if s_puan <= 0:
                break
            doc_id = chunks[i]["doc_id"]
            if doc_id not in best_per_doc:
                best_per_doc[doc_id] = (i, bm25_benzerlik.get(i, 0.0))
                if len(best_per_doc) >= top_n:
                    break

        matches: List[dict] = []
        for i, benzerlik in best_per_doc.values():
            chunk = chunks[i]
            gerekce = self._gerekce_uret(
                chunk, query_tokens, aktif_temalar, evrak_turu, duzeltilmis
            )
            matches.append(self._match_olustur(chunk, round(benzerlik, 3), gerekce))
        # Benzerlik mutlak ölçekte tekdüzedir; nihai benzerliğe göre sırala
        matches.sort(key=lambda m: m["benzerlik"], reverse=True)

        # Mutlak taban eşiği: en iyi eşleşme bile zayıfsa listeyi işaretle
        if matches and matches[0]["benzerlik"] < ZAYIF_ESLESME_ESIGI:
            for m in matches:
                m["zayif_esleme"] = True
            logger.info(
                "Mevzuat araması zayıf eşleşme ile sonuçlandı "
                f"(en iyi benzerlik {matches[0]['benzerlik']}); korpusta "
                "evraka doğrudan uyan hüküm bulunamamış olabilir."
            )
        return matches, yontem

    def _match_olustur(self, chunk: Dict, benzerlik: float, gerekce: str = "") -> dict:
        """
        Chunk'tan standart öneri sözlüğü üretir.

        Şema (P0-1): mevzuat_adi + madde_no + gerekce + benzerlik(skor);
        geriye dönük uyumluluk için eski anahtarlar (baslik, icerik_ozeti,
        kaynak, anahtar_kelimeler) korunur.
        """
        madde_no = list(chunk.get("madde_no", []))
        return {
            "doc_id": chunk["doc_id"],
            "baslik": chunk["baslik"],
            "mevzuat_adi": chunk["baslik"],
            "bolum": chunk["bolum"],
            "madde_no": madde_no,
            "madde_etiketi": madde_etiketi(madde_no),
            "icerik_ozeti": self._chunk_ozeti(chunk),
            "benzerlik": benzerlik,
            "kaynak": chunk["kaynak"],
            "anahtar_kelimeler": chunk["anahtar_kelimeler"],
            "gerekce": gerekce,
        }

    def _gerekce_uret(
        self,
        chunk: Dict,
        query_tokens: List[str],
        aktif_temalar: set,
        evrak_turu: str,
        duzeltilmis: bool = False,
    ) -> str:
        """
        Önerinin NEDEN ilgili olduğunu eşleşme sinyallerinden türetir.

        Halüsinasyon yasağı gereği gerekçe yalnızca gözlenen sinyallerden
        kurulur: sorgu-bölüm ortak ayırt edici terimler (IDF sıralı), tür
        önceliği, aktif alan teması ve düzeltme döngüsü bilgisi.
        """
        parcalar: List[str] = []

        idf = type(self)._bm25.idf if type(self)._bm25 is not None else {}
        chunk_tokens = set(chunk.get("tokens", []))
        ortak = sorted(
            {t for t in query_tokens if t in chunk_tokens},
            key=lambda t: idf.get(t, 0.0),
            reverse=True,
        )[:GEREKCE_TERIM_SAYISI]
        if ortak:
            parcalar.append(
                "eşleşen ayırt edici terimler: " + ", ".join(ortak)
            )

        if evrak_turu and chunk["doc_id"] in TUR_MEVZUAT_AGIRLIKLARI.get(evrak_turu, {}):
            parcalar.append(f"'{evrak_turu}' türü için öncelikli mevzuat")

        tema = ALAN_MEVZUATI.get(chunk["doc_id"])
        if tema is not None and tema in aktif_temalar:
            parcalar.append(f"belgede '{tema}' alan söz dağarcığı saptandı")

        if duzeltilmis:
            parcalar.append(
                "düşük skor sonrası genişletilmiş sorguyla bulundu (düzeltici döngü)"
            )

        return "; ".join(parcalar) if parcalar else "sözcük düzeyinde benzerlik"

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
        raporlanır ve varsa "zayif_esleme" işareti kaldırılır (türsel
        gerekçe metinsel eşleşmenin zayıflığından etkilenmez).
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

        usul_gerekcesi = (
            f"'{evrak_turu}' türündeki her evrak bu mevzuata tabidir (usul mevzuatı)"
        )

        # Liste başına alınan usul mevzuatının benzerliği, mevcut en
        # yüksek benzerlikten (ve 0.8 tabanından) düşük raporlanmaz
        en_yuksek = matches[0]["benzerlik"] if matches else 0.8

        # Listede varsa başa taşı (doc_id ile; eski davranış başlıkla eşliyordu)
        for i, m in enumerate(matches):
            ayni_mevzuat = (
                m.get("doc_id") == doc_id or m.get("baslik") == chunk["baslik"]
            )
            if ayni_mevzuat:
                tasinan = matches.pop(i)
                tasinan["benzerlik"] = round(
                    max(float(tasinan.get("benzerlik") or 0.0), float(en_yuksek), 0.8), 3
                )
                tasinan["eklenme_nedeni"] = "tur_usul_mevzuati"
                tasinan.pop("zayif_esleme", None)
                mevcut_gerekce = tasinan.get("gerekce") or ""
                if usul_gerekcesi not in mevcut_gerekce:
                    tasinan["gerekce"] = (
                        f"{usul_gerekcesi}; {mevcut_gerekce}" if mevcut_gerekce
                        else usul_gerekcesi
                    )
                return [tasinan] + matches

        usul_onerisi = self._match_olustur(
            chunk,
            round(max(float(en_yuksek), 0.8), 3),
            usul_gerekcesi,
        )
        usul_onerisi["eklenme_nedeni"] = "tur_usul_mevzuati"
        return [usul_onerisi] + matches

    def _ensure_kvkk_mevzuati(
        self, matches: List[dict], kvkk_sinyali: bool
    ) -> List[dict]:
        """
        Belgede gerçek kişiye ait kişisel veri (doğrulanmış T.C. kimlik
        numarası / IBAN) saptandıysa 6698 sayılı KVKK'yı öneri listesinin
        ilk üçüne yerleştirir.

        6698'in ilgililiği bu durumda sözcük çakışmasından değil verinin
        kendisinden gelir; "kişisel/kvkk" sözcükleri metinde geçmese bile
        kişisel veri işleniyorsa KVKK uygulanır (usul mevzuatına paralel
        yapısal kesinlik). Enjekte edilen öneri metinsel eşleşme İDDİA
        ETMEZ: benzerliği taslak atıf eşiğinin (0.6) altında raporlanır ve
        eklenme_nedeni="kvkk_veri_sinyali" ile şeffafça işaretlenir.
        Yerleştirme, listede varsa (gerçek benzerliğini koruyarak) ilk üçe
        taşıma, yoksa üçüncü sıraya ekleme biçimindedir; böylece usul
        mevzuatı (sıra 0) ve en iyi metinsel eşleşme (sıra 1) korunur.
        """
        if not kvkk_sinyali:
            return matches

        cls = type(self)
        chunk = next(
            (c for c in (cls._chunks or []) if c["doc_id"] == KVKK_6698_DOC_ID),
            None,
        )
        if chunk is None:
            return matches

        kvkk_gerekcesi = (
            "belgede gerçek kişiye ait kişisel veri (T.C. kimlik numarası / "
            "IBAN) saptandığından 6698 sayılı KVKK'nın işleme (m.5-6) ve "
            "aktarma (m.8) şartları geçerlidir (veri-tespit sinyali; metinsel "
            "eşleşme aranmaz)"
        )

        # Listede varsa: gerçek benzerliğini koru, işaretle ve ilk üçe taşı
        for i, m in enumerate(matches):
            ayni = (
                m.get("doc_id") == KVKK_6698_DOC_ID
                or m.get("baslik") == chunk["baslik"]
            )
            if ayni:
                m["eklenme_nedeni"] = "kvkk_veri_sinyali"
                m.pop("zayif_esleme", None)
                mevcut = m.get("gerekce") or ""
                if "veri-tespit sinyali" not in mevcut:
                    m["gerekce"] = (
                        f"{kvkk_gerekcesi}; {mevcut}" if mevcut else kvkk_gerekcesi
                    )
                if i > 2:
                    matches.insert(2, matches.pop(i))
                return matches

        # Listede yok: üçüncü sıraya ekle (usul + en iyi eşleşme korunur)
        kvkk_onerisi = self._match_olustur(
            chunk, KVKK_SINYAL_BENZERLIK, kvkk_gerekcesi
        )
        kvkk_onerisi["eklenme_nedeni"] = "kvkk_veri_sinyali"
        poz = min(2, len(matches))
        matches.insert(poz, kvkk_onerisi)
        return matches

    # ------------------------------------------------------------------
    # Opsiyonel ChromaDB semantik arama (yedek yol)
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
                        "doc_id": meta.get("doc_id", ""),
                        "baslik": meta.get("baslik", f"Mevzuat #{i + 1}"),
                        "mevzuat_adi": meta.get("baslik", f"Mevzuat #{i + 1}"),
                        "bolum": meta.get("bolum", ""),
                        "madde_no": madde_referanslari(doc),
                        "madde_etiketi": madde_etiketi(madde_referanslari(doc)),
                        "icerik_ozeti": doc[:OZET_LIMITI],
                        "benzerlik": round(max(0.0, 1 - distance), 3),
                        "kaynak": meta.get("kaynak", ""),
                        "anahtar_kelimeler": [],
                        "gerekce": "harici vektör veritabanı (ChromaDB) eşleşmesi",
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
                "doc_id": "resmi_yazisma_yonetmeligi",
                "baslik": "Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik",
                "aciklama": "Tüm resmî yazışmalarda uyulması gereken format ve usul kuralları",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["ust_yazi", "cevap_yazisi", "bilgilendirme", "genelge"],
            },
            {
                "doc_id": "dilekce_hakki_kanunu_3071",
                "baslik": "3071 Sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun",
                "aciklama": "Dilekçede zorunlu bilgiler ve 30 gün içinde cevap verme yükümlülüğü",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["dilekce"],
            },
            {
                "doc_id": "bilgi_edinme_kanunu_4982",
                "baslik": "4982 Sayılı Bilgi Edinme Hakkı Kanunu",
                "aciklama": "Bilgi edinme başvurusu usulü ve 15 iş günlük cevap süresi",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["dilekce", "bilgilendirme", "cevap_yazisi"],
            },
            {
                "doc_id": "devlet_arsiv_hizmetleri_yonetmeligi",
                "baslik": "Devlet Arşiv Hizmetleri Hakkında Yönetmelik",
                "aciklama": "Evrakın arşivlenmesi, saklama süreleri, ayıklama ve imha usulleri",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["ust_yazi", "tutanak", "rapor"],
            },
            {
                "doc_id": "elektronik_imza_kanunu_5070",
                "baslik": "5070 Sayılı Elektronik İmza Kanunu",
                "aciklama": "Güvenli elektronik imzanın hukuki geçerliliği ve elektronik belge",
                "kaynak": "mevzuat.gov.tr (kamuya açık)",
                "ilgili_turler": ["onayli_belge", "ust_yazi", "cevap_yazisi"],
            },
        ]

        matches: List[dict] = []
        for reg in base_regulations:
            if evrak_turu in reg["ilgili_turler"] or not evrak_turu:
                tur_eslesti = evrak_turu in reg["ilgili_turler"]
                matches.append({
                    "doc_id": reg["doc_id"],
                    "baslik": reg["baslik"],
                    "mevzuat_adi": reg["baslik"],
                    "bolum": "",
                    "madde_no": [],
                    "madde_etiketi": "",
                    "icerik_ozeti": reg["aciklama"],
                    "benzerlik": 0.8 if tur_eslesti else 0.3,
                    "kaynak": reg["kaynak"],
                    "anahtar_kelimeler": [],
                    "gerekce": (
                        f"kural tabanlı eşleştirme: '{evrak_turu}' türüyle ilişkili mevzuat"
                        if tur_eslesti
                        else "kural tabanlı eşleştirme: genel mevzuat önerisi"
                    ),
                })

        return sorted(matches, key=lambda x: x["benzerlik"], reverse=True)
