"""
İstatistiksel Sınıflandırıcı — Saf Python Multinomial Naive Bayes.

Evrak türü sınıflandırması için harici bağımlılık gerektirmeyen
(sklearn/numpy YOK) öğrenilmiş istatistiksel model. Kural tabanlı
sınıflandırıcı ile hibrit ensemble kurmak üzere tasarlanmıştır
(bkz. src/agents/classification_agent.py).

Yöntem:
    - Multinomial Naive Bayes, Laplace (add-alpha) düzeltmeli,
      tüm hesaplar log-uzayda (sayısal taşma güvenliği).
    - TF-IDF benzeri ağırlıklandırma: terim frekansı alt-doğrusal
      (1 + ln tf) bastırılır ve düzeltilmiş IDF ile çarpılır. Böylece
      her belgede geçen kalıp sözcükler ("sayı", "konu", "tarih" gibi
      antet dili) değil, türe özgü ayırt edici terimler belirleyici olur.
    - Uzunluk normalizasyonu: belge kanıtı toplam öznitelik ağırlığına
      bölünüp sabit bir kanıt ölçeğiyle çarpılır. Naive Bayes'in
      bağımsızlık varsayımı, birbirine bağımlı öznitelikleri (aynı
      kökün kelime + karakter n-gram görünümleri) tekrar sayarak
      aşırı güvenli (0/1'e doygun) olasılıklar üretir; uzunluk
      normalizasyonu bu bilinen zaafı giderir ve olasılıkları ensemble
      birleşimine uygun ölçeğe getirir (Rennie ve ark. 2003, "Tackling
      the Poor Assumptions of Naive Bayes Text Classifiers").

Öznitelikler:
    1. Kelime token'ları — src.utils.bm25.tokenize (Türkçe'ye uygun
       küçük harf dönüşümü, durak kelime ayıklama).
    2. Karakter 3-gram'ları — kelime sınırı işaretli ("<kelime>").
       Gerekçe: Türkçe sondan eklemeli bir dildir; aynı kök çok sayıda
       çekimle görünür ("başvuru", "başvurunuz", "başvurumun"). Kelime
       düzeyinde bunlar ayrı özniteliklerdir ve küçük eğitim setinde
       seyrekleşir; karakter 3-gram'ları kök/ek örüntülerini paylaşarak
       ek zenginliğine ve OCR gürültüsüne dayanıklılık sağlar.

Model JSON-serileştirilebilir bir sözlüktür (data/processed/ml_model.json);
sınıf düzeyinde (IstatistikselSiniflandirici._cache) mtime duyarlı önbellek
ile yüklenir. Eğitim betiği: scripts/ml_egit.py.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple

from src.utils.bm25 import tokenize

logger = logging.getLogger("kamu_evrak_ajan.istatistiksel_siniflandirici")

# Varsayılan model dosyası (scripts/ml_egit.py bu yola yazar)
VARSAYILAN_MODEL_YOLU = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "processed"
    / "ml_model.json"
)

# Laplace düzeltme katsayısı (add-alpha smoothing; alpha=1 klasik Laplace)
_VARSAYILAN_ALPHA = 1.0

# Karakter n-gram uzunluğu (Türkçe kök+ek örüntüleri için 3 standarttır)
_NGRAM_UZUNLUGU = 3

# Karakter n-gram özniteliklerinin ad alanı öneki (kelime token'ları ile
# çakışmaması için: "arz" kelimesi ile "arz" 3-gram'ı ayrı özniteliklerdir)
_NGRAM_ONEKI = "c3:"

# Kanıt ölçeği (uzunluk normalizasyonu): belge, uzunluğundan bağımsız
# sabit bir kanıt bütçesine sahipmiş gibi puanlanır. Değer, sınıflar arası
# ortalama log-olabilirlik farklarını softmax'te aşırı doygunluğa (0/1)
# götürmeyecek büyüklükte seçilmiştir; geliştirme setinde ensemble
# birleşimine uygun olasılıklar verecek şekilde kalibre edilmiştir.
_KANIT_OLCEGI = 6.0


# ----------------------------------------------------------------------
# Öznitelik çıkarımı
# ----------------------------------------------------------------------


def ozellik_cikar(metin: str) -> Dict[str, int]:
    """
    Metinden öznitelik frekans sözlüğü çıkarır.

    Kelime token'ları (bm25.tokenize) ve kelime sınırı işaretli karakter
    3-gram'ları birlikte sayılır. 3-gram'lar "<" ve ">" sınır işaretleriyle
    üretilir; böylece kelime başı/sonu örüntüleri ("...nız>" gibi iyelik
    ekleri) ayrı sinyal taşır.

    Args:
        metin: Ham evrak metni.

    Returns:
        {öznitelik: frekans} sözlüğü (boş metin için boş sözlük).
    """
    ozellikler: Dict[str, int] = {}
    for token in tokenize(metin or ""):
        ozellikler[token] = ozellikler.get(token, 0) + 1
        sinirli = f"<{token}>"
        for i in range(len(sinirli) - _NGRAM_UZUNLUGU + 1):
            gram = _NGRAM_ONEKI + sinirli[i : i + _NGRAM_UZUNLUGU]
            ozellikler[gram] = ozellikler.get(gram, 0) + 1
    return ozellikler


# ----------------------------------------------------------------------
# Eğitim
# ----------------------------------------------------------------------


def egit(
    dokumanlar: List[Tuple[str, str]], alpha: float = _VARSAYILAN_ALPHA
) -> dict:
    """
    Multinomial Naive Bayes modelini eğitir.

    Her belgenin öznitelik frekansları alt-doğrusal TF (1 + ln tf) ve
    düzeltilmiş IDF (ln((N+1)/(df+1)) + 1) ile ağırlıklandırılıp sınıf
    koşullu ağırlık toplamlarına eklenir. Log-olasılıklar Laplace
    düzeltmesiyle hesaplanır; yalnızca sınıfta gözlenen öznitelikler
    saklanır (gözlenmeyenlerin ortak değeri bilinmeyen_log_olasilik'tir —
    bu, JSON model dosyasını kayıpsız biçimde küçültür).

    Args:
        dokumanlar: (metin, etiket) ikilileri listesi.
        alpha: Laplace düzeltme katsayısı (> 0).

    Returns:
        JSON-serileştirilebilir model sözlüğü:
        {surum, yontem, alpha, belge_sayisi, sinif_belge_sayilari,
         sozluk_boyutu, log_oncul, idf, log_olasilik,
         bilinmeyen_log_olasilik}

    Raises:
        ValueError: Belge listesi boşsa veya alpha <= 0 ise.
    """
    if not dokumanlar:
        raise ValueError("Eğitim için en az bir (metin, etiket) ikilisi gerekir.")
    if alpha <= 0:
        raise ValueError(f"Laplace katsayısı pozitif olmalıdır (alpha={alpha}).")

    belge_sayisi = len(dokumanlar)

    # 1) Belge başına öznitelikler + belge frekansları (df) + sınıf sayıları
    belge_ozellikleri: List[Tuple[Dict[str, int], str]] = []
    df: Dict[str, int] = {}
    sinif_belge_sayilari: Dict[str, int] = {}
    for metin, etiket in dokumanlar:
        ozellikler = ozellik_cikar(metin)
        belge_ozellikleri.append((ozellikler, etiket))
        sinif_belge_sayilari[etiket] = sinif_belge_sayilari.get(etiket, 0) + 1
        for ozellik in ozellikler:
            df[ozellik] = df.get(ozellik, 0) + 1

    # 2) Düzeltilmiş IDF (her terime pozitif değer garanti eden varyant)
    idf: Dict[str, float] = {
        ozellik: math.log((belge_sayisi + 1) / (n + 1)) + 1.0
        for ozellik, n in df.items()
    }

    # 3) Sınıf koşullu TF-IDF ağırlık toplamları
    sinif_agirliklari: Dict[str, Dict[str, float]] = {
        sinif: {} for sinif in sinif_belge_sayilari
    }
    for ozellikler, etiket in belge_ozellikleri:
        hedef = sinif_agirliklari[etiket]
        for ozellik, tf in ozellikler.items():
            agirlik = (1.0 + math.log(tf)) * idf[ozellik]
            hedef[ozellik] = hedef.get(ozellik, 0.0) + agirlik

    # 4) Laplace düzeltmeli log-olasılıklar (log-uzay)
    sozluk_boyutu = len(df)
    log_olasilik: Dict[str, Dict[str, float]] = {}
    bilinmeyen_log_olasilik: Dict[str, float] = {}
    for sinif, agirliklar in sinif_agirliklari.items():
        payda = sum(agirliklar.values()) + alpha * sozluk_boyutu
        log_olasilik[sinif] = {
            ozellik: round(math.log((agirlik + alpha) / payda), 6)
            for ozellik, agirlik in agirliklar.items()
        }
        # Sınıfta hiç gözlenmemiş sözlük terimlerinin ortak log-olasılığı
        bilinmeyen_log_olasilik[sinif] = round(math.log(alpha / payda), 6)

    log_oncul = {
        sinif: round(math.log(adet / belge_sayisi), 6)
        for sinif, adet in sinif_belge_sayilari.items()
    }

    logger.info(
        f"Model eğitildi: {belge_sayisi} belge, {len(sinif_belge_sayilari)} sınıf, "
        f"{sozluk_boyutu} öznitelik."
    )
    return {
        "surum": 1,
        "yontem": "multinomial_nb_tfidf",
        "alpha": alpha,
        "belge_sayisi": belge_sayisi,
        "sinif_belge_sayilari": sinif_belge_sayilari,
        "sozluk_boyutu": sozluk_boyutu,
        "log_oncul": log_oncul,
        "idf": {ozellik: round(deger, 6) for ozellik, deger in idf.items()},
        "log_olasilik": log_olasilik,
        "bilinmeyen_log_olasilik": bilinmeyen_log_olasilik,
    }


# ----------------------------------------------------------------------
# Tahmin
# ----------------------------------------------------------------------


def tahmin(model: dict, metin: str) -> Tuple[str, Dict[str, float]]:
    """
    Eğitilmiş modelle metni sınıflandırır.

    Log-uzayda skorlama: her sınıf için log-öncül + uzunluk normalize
    edilmiş kanıt (TF-IDF ağırlıklı log-olabilirlik ortalaması x kanıt
    ölçeği). Sözlük dışı (eğitimde hiç görülmemiş) öznitelikler atlanır
    — sınıflar arası ayrımda kanıt taşımazlar. Sözlükte olup sınıfta
    gözlenmemiş öznitelikler Laplace tabanlı bilinmeyen_log_olasilik ile
    puanlanır. Skorlar log-sum-exp ile olasılık dağılımına çevrilir.

    Hiç bilinen öznitelik yoksa (boş metin / tamamen sözlük dışı metin)
    sonsal dağılım öncüle eşittir: en sık sınıf düşük güvenle döner.

    Args:
        model: egit() çıktısı (veya JSON'dan yüklenmiş eşdeğeri).
        metin: Sınıflandırılacak metin.

    Returns:
        (en_olasi_tur, {tur: olasilik}) ikilisi; olasılıklar 1'e toplanır.

    Raises:
        ValueError: Model gerekli alanları içermiyorsa.
    """
    log_oncul: Dict[str, float] = model.get("log_oncul") or {}
    if not log_oncul:
        raise ValueError("Geçersiz model: 'log_oncul' alanı boş veya eksik.")
    idf: Dict[str, float] = model.get("idf") or {}
    log_olasilik: Dict[str, Dict[str, float]] = model.get("log_olasilik") or {}
    bilinmeyen: Dict[str, float] = model.get("bilinmeyen_log_olasilik") or {}

    ozellikler = ozellik_cikar(metin)

    # Sözlükteki özniteliklerin TF-IDF ağırlıkları (sözlük dışı atlanır)
    agirliklar: Dict[str, float] = {}
    for ozellik, tf in ozellikler.items():
        idf_degeri = idf.get(ozellik)
        if idf_degeri is None:
            continue
        agirliklar[ozellik] = (1.0 + math.log(tf)) * idf_degeri
    toplam_agirlik = sum(agirliklar.values())

    skorlar: Dict[str, float] = {}
    for sinif, oncul in log_oncul.items():
        skor = float(oncul)
        if toplam_agirlik > 0:
            sinif_olasiliklari = log_olasilik.get(sinif, {})
            sinif_bilinmeyen = bilinmeyen.get(sinif, -20.0)
            kanit = 0.0
            for ozellik, agirlik in agirliklar.items():
                kanit += agirlik * sinif_olasiliklari.get(ozellik, sinif_bilinmeyen)
            # Uzunluk normalizasyonu: kanıt ortalaması x sabit ölçek
            skor += _KANIT_OLCEGI * (kanit / toplam_agirlik)
        skorlar[sinif] = skor

    # Log-sum-exp ile sayısal güvenli normalizasyon
    en_yuksek = max(skorlar.values())
    usler = {sinif: math.exp(skor - en_yuksek) for sinif, skor in skorlar.items()}
    toplam = sum(usler.values()) or 1.0
    olasiliklar = {sinif: deger / toplam for sinif, deger in usler.items()}

    en_olasi = max(olasiliklar, key=lambda sinif: olasiliklar[sinif])
    return en_olasi, olasiliklar


# ----------------------------------------------------------------------
# Serileştirme ve önbellekli yükleme
# ----------------------------------------------------------------------


def model_kaydet(model: dict, yol: Optional[Path] = None) -> Path:
    """
    Modeli JSON dosyasına yazar.

    Args:
        model: egit() çıktısı.
        yol: Hedef dosya (varsayılan: data/processed/ml_model.json).

    Returns:
        Yazılan dosyanın yolu.
    """
    hedef = Path(yol) if yol is not None else VARSAYILAN_MODEL_YOLU
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(
        json.dumps(model, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    logger.info(f"Model kaydedildi: {hedef}")
    return hedef


class IstatistikselSiniflandirici:
    """
    Eğitilmiş modeli diskten yükleyip sınıf düzeyinde önbellekleyen katman.

    Önbellek mtime duyarlıdır: model dosyası yeniden eğitilirse (mtime
    değişirse) bir sonraki yükleme taze içeriği okur; aksi halde aynı
    süreçteki tüm agent örnekleri tek kopyayı paylaşır.
    """

    # {mutlak_yol: (mtime, model)} — sınıf düzeyinde paylaşılan önbellek
    _cache: ClassVar[Dict[str, Tuple[float, dict]]] = {}

    _GEREKLI_ALANLAR = ("log_oncul", "idf", "log_olasilik", "bilinmeyen_log_olasilik")

    @classmethod
    def yukle(cls, yol: Optional[Path] = None) -> Optional[dict]:
        """
        Model dosyasını yükler; dosya yoksa/bozuksa None döndürür.

        Çağıran taraf None durumunda saf kural tabanlı moda düşer
        (zarif bozulma — sistem modelsiz de tam çalışır).
        """
        hedef = Path(yol) if yol is not None else VARSAYILAN_MODEL_YOLU
        try:
            mtime = hedef.stat().st_mtime
        except OSError:
            return None

        anahtar = str(hedef.resolve())
        onbellek = cls._cache.get(anahtar)
        if onbellek is not None and onbellek[0] == mtime:
            return onbellek[1]

        try:
            model = json.loads(hedef.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Model dosyası okunamadı ({hedef}): {exc}")
            return None

        if not isinstance(model, dict) or any(
            alan not in model for alan in cls._GEREKLI_ALANLAR
        ):
            logger.warning(f"Model dosyası geçersiz şemada, yok sayılıyor: {hedef}")
            return None

        cls._cache[anahtar] = (mtime, model)
        logger.info(
            f"İstatistiksel model yüklendi: {hedef.name} "
            f"({model.get('belge_sayisi', '?')} belge, "
            f"{model.get('sozluk_boyutu', '?')} öznitelik)"
        )
        return model

    @classmethod
    def onbellek_temizle(cls) -> None:
        """Önbelleği boşaltır (testler ve yeniden eğitim senaryoları için)."""
        cls._cache.clear()
