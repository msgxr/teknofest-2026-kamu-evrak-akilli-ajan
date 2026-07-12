"""
Değerlendirme Aracı — Ölçülebilir başarım raporu üretir.

Şartname Referansı:
    "Puanlamada sınıflandırma doğruluğu, yönlendirme başarımı,
     özet/şablon kalitesi ve eksik bilgi tespiti ölçülecektir.
     Gerçek zamana yakın çalışma avantaj sağlayacaktır."

Bu araç, data/raw/kurgu_evraklar/etiketler.json içindeki etiketli
kurgu evrakları uçtan uca pipeline ile işler ve dört metrik grubu üretir:

    1. Sınıflandırma: accuracy, tür bazında precision/recall/F1, macro-F1,
       yanlış sınıflananların listesi (confusion özeti)
    2. Yönlendirme: accuracy (yonlendirme.birim_kodu == etiket birim_kodu),
       yanlış yönlendirmeler listesi
    3. Eksik bilgi tespiti: alan bazında set karşılaştırması ile
       micro precision/recall/F1
    4. Mevzuat önerisi: isabet@3 / isabet@1 (etiketlerdeki opsiyonel
       "mevzuat_beklenen" doc_id listesinden en az biri ilk k öneride
       geçiyorsa isabet; etiketsiz evraklar bu metriğe katılmaz)
    5. Performans: evrak başına ortalama/medyan işlem süresi ve
       adım bazında ortalama süreler (gerçek zamana yakınlık kanıtı)

Çıktılar:
    - Konsol raporu (rich Table)
    - data/processed/eval_report.json (tüm metrikler + zaman damgası
      + LLM backend bilgisi)

Kullanım:
    python3 scripts/evaluate.py                  # tüm etiketli dosyalar
    python3 scripts/evaluate.py --limit 5        # ilk 5 dosya
    python3 scripts/evaluate.py --dosya x.txt    # tek dosya
    python3 scripts/evaluate.py --json-only      # sadece JSON çıktısı

    # Held-out (tutulmuş) set üzerinde dış geçerlilik ölçümü:
    python3 scripts/evaluate.py \
        --veri-dizini data/raw/kurgu_evraklar_heldout \
        --rapor-dosyasi data/processed/eval_report_heldout.json

--veri-dizini, içinde etiketler.json ve .txt evrakları bulunan herhangi
bir dizine yöneltilebilir (varsayılan: data/raw/kurgu_evraklar —
geliştirme seti). Rapor JSON'undaki "veri_dizini" ve "set_adi" alanları
hangi set üzerinde ölçüm yapıldığını kalıcı olarak belgeler.

Not: Metrik fonksiyonları saf Python'dur (sklearn YOK) ve pipeline
çalıştırılmadan import edilebilir — birim testleri bu fonksiyonları
doğrudan test eder (tests/test_evaluation.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Proje kökünü sys.path'e ekle (script doğrudan çalıştırıldığında gerekli)
PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

logger = logging.getLogger("kamu_evrak_ajan.evaluate")

# Varsayılan yollar (CLI'daki --veri-dizini / --rapor-dosyasi ile değiştirilebilir)
EVRAK_DIZINI = PROJE_KOKU / "data" / "raw" / "kurgu_evraklar"
ETIKET_DOSYASI = EVRAK_DIZINI / "etiketler.json"
RAPOR_DOSYASI = PROJE_KOKU / "data" / "processed" / "eval_report.json"


def goreli_yol(yol: Any) -> str:
    """
    Yolu proje köküne göre göreli dizeye çevirir.

    # GÜVENLİK: rapor JSON'u git ile izlenir; mutlak yol (makine/kullanıcı
    # adı) sızmaması için yol her koşulda köke göre göreli yazılır, kök
    # dışındaki yollar için yalnızca dizin adı raporlanır.
    """
    p = Path(yol).resolve()
    try:
        return p.relative_to(PROJE_KOKU).as_posix()
    except ValueError:
        return p.name


# ---------------------------------------------------------------------------
# SAF METRİK FONKSİYONLARI (pipeline'dan bağımsız, birim testlenebilir)
# ---------------------------------------------------------------------------

def hesapla_accuracy(gercek: Sequence[str], tahmin: Sequence[str]) -> float:
    """
    Basit doğruluk oranı: doğru tahmin sayısı / toplam örnek sayısı.

    Args:
        gercek: Gerçek (etiket) değerler listesi
        tahmin: Tahmin edilen değerler listesi (aynı uzunlukta)

    Returns:
        0.0–1.0 aralığında doğruluk oranı (boş girişte 0.0)
    """
    if not gercek or len(gercek) != len(tahmin):
        return 0.0
    dogru = sum(1 for g, t in zip(gercek, tahmin) if g == t)
    return dogru / len(gercek)


def hesapla_sinif_metrikleri(
    gercek: Sequence[str], tahmin: Sequence[str]
) -> Dict[str, Any]:
    """
    Sınıf bazında precision/recall/F1 ve macro-F1 hesaplar (saf Python).

    Args:
        gercek: Gerçek sınıf etiketleri
        tahmin: Tahmin edilen sınıf etiketleri

    Returns:
        {
            "sinif_bazinda": {sinif: {"precision", "recall", "f1", "destek"}},
            "macro_f1": float,
            "macro_precision": float,
            "macro_recall": float,
        }
    """
    siniflar = sorted(set(gercek) | set(tahmin))
    sinif_bazinda: Dict[str, Dict[str, float]] = {}
    p_toplam = r_toplam = f1_toplam = 0.0

    for sinif in siniflar:
        tp = sum(1 for g, t in zip(gercek, tahmin) if g == sinif and t == sinif)
        fp = sum(1 for g, t in zip(gercek, tahmin) if g != sinif and t == sinif)
        fn = sum(1 for g, t in zip(gercek, tahmin) if g == sinif and t != sinif)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        sinif_bazinda[sinif] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "destek": tp + fn,  # gerçek etikette bu sınıftan kaç örnek var
        }
        p_toplam += precision
        r_toplam += recall
        f1_toplam += f1

    n = len(siniflar)
    return {
        "sinif_bazinda": sinif_bazinda,
        "macro_precision": round(p_toplam / n, 4) if n else 0.0,
        "macro_recall": round(r_toplam / n, 4) if n else 0.0,
        "macro_f1": round(f1_toplam / n, 4) if n else 0.0,
    }


def hesapla_set_metrikleri(
    ciftler: Sequence[Tuple[Set[str], Set[str]]]
) -> Dict[str, float]:
    """
    Set karşılaştırmasıyla micro precision/recall/F1 hesaplar.

    Eksik bilgi tespiti değerlendirmesi için kullanılır: her evrak için
    (beklenen eksik alanlar kümesi, tahmin edilen eksik alanlar kümesi)
    çifti verilir; TP/FP/FN tüm evraklar üzerinden toplanır (micro).

    Args:
        ciftler: (gercek_kume, tahmin_kume) çiftleri listesi

    Returns:
        {"micro_precision", "micro_recall", "micro_f1", "tp", "fp", "fn"}
    """
    tp = fp = fn = 0
    for gercek_kume, tahmin_kume in ciftler:
        gercek_kume = set(gercek_kume)
        tahmin_kume = set(tahmin_kume)
        tp += len(gercek_kume & tahmin_kume)
        fp += len(tahmin_kume - gercek_kume)
        fn += len(gercek_kume - tahmin_kume)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "micro_precision": round(precision, 4),
        "micro_recall": round(recall, 4),
        "micro_f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def hesapla_isabet_at_k(
    ciftler: Sequence[Tuple[Set[str], Sequence[str]]], k: int = 3
) -> Dict[str, Any]:
    """
    Mevzuat önerisi isabet@k oranını hesaplar (saf Python).

    Her evrak için (beklenen doc_id kümesi, tahmin edilen sıralı doc_id
    listesi) çifti verilir. Beklenen kümesi BOŞ olan evraklar metriğe
    KATILMAZ (etiketsiz sayılır). Bir evrak, beklenen mevzuatlardan en az
    biri ilk k öneride geçiyorsa isabetli sayılır (hit-rate@k).

    Args:
        ciftler: (beklenen_kume, tahmin_sirali_listesi) çiftleri
        k: İlk kaç önerinin dikkate alınacağı

    Returns:
        {"k", "etiketli_evrak", "isabet", "isabet_orani"} —
        isabet_orani etiketli evrak yoksa None (0.0 ile karışmasın diye)
    """
    etiketli = [
        (set(beklenen), list(tahmin))
        for beklenen, tahmin in ciftler
        if beklenen
    ]
    isabet = sum(
        1 for beklenen, tahmin in etiketli if beklenen & set(tahmin[:k])
    )
    return {
        "k": k,
        "etiketli_evrak": len(etiketli),
        "isabet": isabet,
        "isabet_orani": (
            round(isabet / len(etiketli), 4) if etiketli else None
        ),
    }


def hesapla_siralama_metrikleri(
    ciftler: Sequence[Tuple[Set[str], Sequence[str]]], k: int = 3
) -> Dict[str, Any]:
    """RAGAS-tarzı getirim sıralama metrikleri: MRR@k, nDCG@k, context
    precision@k, context recall@k (saf Python).

    isabet@k yalnızca "ilk k'da var mı" der; bu metrikler doğru mevzuatın
    KAÇINCI sırada olduğunu (MRR/nDCG) ve getirilen bağlamın tamlığını
    (precision/recall) ölçer — getirim kalitesinin sıralama-duyarlı görünümü.

    Literatür: Järvelin & Kekäläinen (2002) nDCG; Mean Reciprocal Rank
    (klasik IR); RAGAS (Es vd. 2023) context precision/recall.

    Beklenen kümesi boş olan evraklar metriğe katılmaz (isabet@k ile aynı).
    """
    etiketli = [
        (set(beklenen), list(tahmin)) for beklenen, tahmin in ciftler if beklenen
    ]
    if not etiketli:
        return {
            "k": k, "etiketli_evrak": 0, "mrr": None, "ndcg": None,
            "context_precision": None, "context_recall": None,
        }
    mrr_top = ndcg_top = cp_top = cr_top = 0.0
    for beklenen, tahmin in etiketli:
        ilk_k = tahmin[:k]
        # MRR: ilk ilgili önerinin ters sırası (1/rank)
        rr = 0.0
        for i, doc in enumerate(ilk_k):
            if doc in beklenen:
                rr = 1.0 / (i + 1)
                break
        mrr_top += rr
        # nDCG: ikili ilgililik, konum indirimli
        dcg = sum(
            1.0 / math.log2(i + 2) for i, doc in enumerate(ilk_k) if doc in beklenen
        )
        ideal_n = min(len(beklenen), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_n))
        ndcg_top += (dcg / idcg) if idcg > 0 else 0.0
        # Bağlam precision@k (getirilenin ne kadarı ilgili) / recall@k
        # (ilgililerin ne kadarı getirildi)
        ilgili_getirilen = sum(1 for doc in ilk_k if doc in beklenen)
        cp_top += (ilgili_getirilen / len(ilk_k)) if ilk_k else 0.0
        cr_top += ilgili_getirilen / len(beklenen)
    n = len(etiketli)
    return {
        "k": k,
        "etiketli_evrak": n,
        "mrr": round(mrr_top / n, 4),
        "ndcg": round(ndcg_top / n, 4),
        "context_precision": round(cp_top / n, 4),
        "context_recall": round(cr_top / n, 4),
    }


def hesapla_isabet_kacaklari(
    dosyalar: Sequence[str],
    beklenenler: Sequence[Set[str]],
    tahminler: Sequence[Sequence[str]],
    k: int = 3,
) -> List[Dict[str, Any]]:
    """
    isabet@k'da kaçırılan evrakların listesini üretir (hata analizi için).

    Returns:
        [{"dosya", "beklenen", "tahmin"}] — yalnızca etiketli VE ilk k
        öneride beklenen mevzuatı hiç içermeyen evraklar için
    """
    return [
        {"dosya": d, "beklenen": sorted(b), "tahmin": list(t[:k])}
        for d, b, t in zip(dosyalar, beklenenler, tahminler)
        if b and not (set(b) & set(list(t)[:k]))
    ]


def hesapla_confusion_matrix(
    gercek: Sequence[str], tahmin: Sequence[str]
) -> Dict[str, Any]:
    """
    Tür bazında karışıklık (confusion) matrisi üretir (saf Python).

    Args:
        gercek: Gerçek sınıf etiketleri
        tahmin: Tahmin edilen sınıf etiketleri (aynı uzunlukta)

    Returns:
        {"siniflar": [...sıralı sınıf listesi...],
         "matris": {gercek_sinif: {tahmin_sinif: sayi}}}
        — satır gerçek etiketi, sütun tahmini temsil eder; köşegen
        dışındaki her hücre bir karışma desenidir (hata analizi girdisi).
    """
    siniflar = sorted(set(gercek) | set(tahmin))
    matris: Dict[str, Dict[str, int]] = {
        g: {t: 0 for t in siniflar} for g in siniflar
    }
    for g, t in zip(gercek, tahmin):
        matris[g][t] += 1
    return {"siniflar": siniflar, "matris": matris}


def hesapla_taslak_kalitesi(sonuclar: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Taslak kalite hakemi puanlarının (0-100) özet istatistiğini üretir.

    Args:
        sonuclar: evraklari_isle() çıktısı ("taslak_puan"/"taslak_yontem"
            alanları kullanılır; puanı olmayan sonuçlar dışlanır)

    Returns:
        {"ortalama_puan", "asgari_puan", "degerlendirilen", "yontemler"}
        — hiç puan yoksa ortalama/asgari None
    """
    puanlar = [
        float(s["taslak_puan"]) for s in sonuclar
        if s.get("taslak_puan") is not None
    ]
    yontemler: Dict[str, int] = {}
    for s in sonuclar:
        yontem = str(s.get("taslak_yontem") or "").strip()
        if yontem:
            yontemler[yontem] = yontemler.get(yontem, 0) + 1
    return {
        "ortalama_puan": round(sum(puanlar) / len(puanlar), 1) if puanlar else None,
        "asgari_puan": round(min(puanlar), 1) if puanlar else None,
        "degerlendirilen": len(puanlar),
        "yontemler": yontemler,
    }


def hesapla_medyan(degerler: Sequence[float]) -> float:
    """
    Medyan hesaplar (saf Python, statistics modülüne bile gerek yok).

    Args:
        degerler: Sayısal değerler listesi

    Returns:
        Medyan değer (boş listede 0.0)
    """
    if not degerler:
        return 0.0
    sirali = sorted(degerler)
    n = len(sirali)
    orta = n // 2
    if n % 2 == 1:
        return float(sirali[orta])
    return (sirali[orta - 1] + sirali[orta]) / 2.0


def hesapla_yanlis_listesi(
    dosyalar: Sequence[str], gercek: Sequence[str], tahmin: Sequence[str]
) -> List[Dict[str, str]]:
    """
    Yanlış tahminlerin listesini üretir (confusion özeti).

    Args:
        dosyalar: Dosya adları
        gercek: Gerçek etiketler
        tahmin: Tahminler

    Returns:
        [{"dosya", "beklenen", "tahmin"}] yalnızca yanlışlar için
    """
    return [
        {"dosya": d, "beklenen": g, "tahmin": t}
        for d, g, t in zip(dosyalar, gercek, tahmin)
        if g != t
    ]


def hesapla_adim_ortalamalari(
    tum_adimlar: Sequence[Sequence[Dict[str, Any]]]
) -> Dict[str, float]:
    """
    Adım (agent) bazında ortalama işlem sürelerini hesaplar.

    Args:
        tum_adimlar: Her evrak için islem_adimlari listesi
                     (her adım: {"agent", "sure_saniye", ...})

    Returns:
        {agent_adi: ortalama_sure_saniye}
    """
    toplamlar: Dict[str, float] = {}
    sayilar: Dict[str, int] = {}
    for adimlar in tum_adimlar:
        for adim in adimlar:
            agent = adim.get("agent", "bilinmiyor")
            sure = float(adim.get("sure_saniye", 0.0))
            toplamlar[agent] = toplamlar.get(agent, 0.0) + sure
            sayilar[agent] = sayilar.get(agent, 0) + 1
    return {
        agent: round(toplamlar[agent] / sayilar[agent], 4)
        for agent in toplamlar
    }


# ---------------------------------------------------------------------------
# DEĞERLENDİRME AKIŞI
# ---------------------------------------------------------------------------

def etiketleri_yukle(etiket_yolu: Path) -> Dict[str, dict]:
    """
    Etiket dosyasını yükler; yoksa anlaşılır mesajla programı sonlandırır.

    Beklenen format:
        {"dosya.txt": {"tur", "birim_kodu", "eksik_alanlar": [...], "aciklama",
                       "mevzuat_beklenen": [...] (opsiyonel, doc_id listesi)}}
    """
    if not etiket_yolu.exists():
        print(
            "HATA: Etiket dosyası bulunamadı: {}\n"
            "Değerlendirme için önce etiketli kurgu evrak seti oluşturulmalı.\n"
            "Beklenen format: {{\"dosya.txt\": {{\"tur\": ..., \"birim_kodu\": ..., "
            "\"eksik_alanlar\": [...], \"aciklama\": ...}}}}".format(etiket_yolu),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(etiket_yolu, encoding="utf-8") as f:
            etiketler = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"HATA: Etiket dosyası okunamadı ({etiket_yolu}): {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(etiketler, dict) or not etiketler:
        print(f"HATA: Etiket dosyası boş veya geçersiz formatta: {etiket_yolu}", file=sys.stderr)
        sys.exit(1)

    return etiketler


def llm_bilgisi_al() -> Dict[str, Any]:
    """Raporda gösterilecek LLM backend bilgisini toplar (hata toleranslı)."""
    try:
        from src.models.llm_wrapper import get_default_llm

        llm = get_default_llm()
        return {
            "backend": getattr(llm, "backend", "bilinmiyor"),
            "model": getattr(llm, "model_name", ""),
            "kullanilabilir": bool(llm.is_available()),
        }
    except Exception as e:  # LLM tamamen erişilemezse bile rapor üretilmeli
        logger.warning(f"LLM bilgisi alınamadı: {e}")
        return {"backend": "offline", "model": "", "kullanilabilir": False}


def evraklari_isle(
    etiketler: Dict[str, dict],
    limit: Optional[int] = None,
    tek_dosya: Optional[str] = None,
    evrak_dizini: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Etiketli evrakları uçtan uca pipeline ile işler.

    Args:
        etiketler: {dosya_adi: etiket_sozlugu}
        limit: İlk N dosyayı işle (None → hepsi)
        tek_dosya: Sadece bu dosyayı işle
        evrak_dizini: Evrak .txt dosyalarının bulunduğu dizin
                      (None → varsayılan geliştirme seti dizini)

    Returns:
        (sonuclar, islenemeyenler) — sonuclar: her evrak için
        {"dosya", "etiket", "tahmin_tur", "tahmin_birim",
         "tahmin_eksik": set, "adimlar": [...], "toplam_sure": float}
    """
    # Pipeline importu bilinçli olarak gecikmeli: metrik fonksiyonları
    # pipeline yüklenmeden import edilebilsin (birim testleri için).
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    if evrak_dizini is None:
        evrak_dizini = EVRAK_DIZINI

    dosya_adlari = sorted(etiketler.keys())
    if tek_dosya is not None:
        if tek_dosya not in etiketler:
            print(
                f"HATA: '{tek_dosya}' etiket dosyasında bulunamadı. "
                f"Etiketli dosyalar: {', '.join(dosya_adlari)}",
                file=sys.stderr,
            )
            sys.exit(1)
        dosya_adlari = [tek_dosya]
    if limit is not None:
        dosya_adlari = dosya_adlari[: max(0, limit)]

    pipeline = EndToEndPipeline()
    sonuclar: List[Dict[str, Any]] = []
    islenemeyenler: List[Dict[str, str]] = []

    for i, dosya_adi in enumerate(dosya_adlari, 1):
        dosya_yolu = evrak_dizini / dosya_adi
        logger.info(f"[{i}/{len(dosya_adlari)}] İşleniyor: {dosya_adi}")

        if not dosya_yolu.exists():
            islenemeyenler.append({"dosya": dosya_adi, "hata": "Dosya bulunamadı"})
            continue

        try:
            result = pipeline.process(str(dosya_yolu), mode="full")
        except Exception as e:
            logger.error(f"Pipeline hatası ({dosya_adi}): {e}")
            islenemeyenler.append({"dosya": dosya_adi, "hata": str(e)})
            continue

        adimlar = result.get("islem_adimlari", []) or []
        toplam_sure = sum(float(a.get("sure_saniye", 0.0)) for a in adimlar)

        siniflandirma = result.get("siniflandirma") or {}
        sonuclar.append({
            "dosya": dosya_adi,
            "etiket": etiketler[dosya_adi],
            "tahmin_tur": siniflandirma.get("tur", "diger"),
            "tahmin_guven": float(siniflandirma.get("guven", 0.0)),
            "tahmin_olasiliklar": siniflandirma.get("tum_skorlar") or {},
            "tahmin_birim": (result.get("yonlendirme") or {}).get("birim_kodu", ""),
            "tahmin_eksik": {
                e.get("alan", "")
                for e in (result.get("eksik_bilgiler") or [])
                if e.get("alan")
            },
            "tahmin_mevzuat": [
                m.get("doc_id", "")
                for m in (result.get("mevzuat_eslestirme") or [])
                if m.get("doc_id")
            ],
            "taslak_puan": (result.get("taslak_kalitesi") or {}).get("puan"),
            "taslak_yontem": (result.get("taslak_kalitesi") or {}).get("yontem", ""),
            "tahmin_ozet": result.get("ozet", "") or "",
            "kaynak_metin": (
                dosya_yolu.read_text(encoding="utf-8", errors="ignore")
                if dosya_yolu.suffix.lower() == ".txt" else ""
            ),
            "adimlar": adimlar,
            "toplam_sure": round(toplam_sure, 4),
        })

    return sonuclar, islenemeyenler


def metrikleri_hesapla(
    sonuclar: List[Dict[str, Any]],
    islenemeyenler: List[Dict[str, str]],
    veri_dizini: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Toplanan pipeline sonuçlarından tüm metrik gruplarını hesaplar.

    Args:
        sonuclar: evraklari_isle() çıktısı
        islenemeyenler: İşlenemeyen dosya listesi
        veri_dizini: Değerlendirilen veri setinin dizini; rapora
                     "veri_dizini" ve "set_adi" olarak yazılır
                     (None → varsayılan geliştirme seti dizini)
    """
    if veri_dizini is None:
        veri_dizini = EVRAK_DIZINI
    dosyalar = [s["dosya"] for s in sonuclar]

    # 1. Sınıflandırma
    gercek_tur = [s["etiket"].get("tur", "diger") for s in sonuclar]
    tahmin_tur = [s["tahmin_tur"] for s in sonuclar]
    sinif_metrikleri = hesapla_sinif_metrikleri(gercek_tur, tahmin_tur)

    # 2. Yönlendirme
    gercek_birim = [s["etiket"].get("birim_kodu", "") for s in sonuclar]
    tahmin_birim = [s["tahmin_birim"] for s in sonuclar]

    # 3. Eksik bilgi tespiti (set karşılaştırması)
    eksik_ciftler = [
        (set(s["etiket"].get("eksik_alanlar", []) or []), s["tahmin_eksik"])
        for s in sonuclar
    ]

    # 4. Mevzuat önerisi (isabet@k — yalnızca mevzuat_beklenen etiketi
    #    bulunan evraklar üzerinden hesaplanır)
    beklenen_mevzuat = [
        set(s["etiket"].get("mevzuat_beklenen", []) or []) for s in sonuclar
    ]
    tahmin_mevzuat = [s.get("tahmin_mevzuat", []) for s in sonuclar]
    mevzuat_ciftler = list(zip(beklenen_mevzuat, tahmin_mevzuat))

    # 5. Performans
    sureler = [s["toplam_sure"] for s in sonuclar]
    ortalama_sure = round(sum(sureler) / len(sureler), 4) if sureler else 0.0

    # 6. Güven kalibrasyonu (ECE / MCE / Brier / reliability / risk-coverage)
    from src.utils.kalibrasyon import kalibrasyon_raporu
    set_adi = Path(veri_dizini).name
    kalibre_guvenler = [float(s.get("tahmin_guven", 0.0)) for s in sonuclar]
    kalibre_dogrular = [t == g for t, g in zip(tahmin_tur, gercek_tur)]
    kalibre_olasiliklar = [s.get("tahmin_olasiliklar") or {} for s in sonuclar]
    # Sıcaklık öğrenimi YALNIZCA geliştirme setinde; held-out setlerde yalnızca
    # ölçüm yapılır (değerlendirme bütünlüğü — teknik_rapor §5 kuralı).
    kalibrasyon = kalibrasyon_raporu(
        kalibre_guvenler,
        kalibre_dogrular,
        olasilik_listesi=kalibre_olasiliklar,
        dogru_siniflar=gercek_tur,
        sicaklik_ogren_izinli=(set_adi == "kurgu_evraklar"),
    )

    # 6b. Seçici sınıflandırma (reject option): 0,6 eşiğinde kapsama/risk +
    #     ortalama belirsizlik (MSP+marj). İnsan-onayı kapısının fayda kanıtı.
    from src.utils.secici_tahmin import belirsizlik_skoru, kapsam_risk
    secici_tahmin = kapsam_risk(kalibre_guvenler, kalibre_dogrular, esik=0.6)
    _belirsizlikler = [
        belirsizlik_skoru(o)["belirsizlik"] for o in kalibre_olasiliklar if o
    ]
    secici_tahmin["ortalama_belirsizlik"] = (
        round(sum(_belirsizlikler) / len(_belirsizlikler), 4)
        if _belirsizlikler else None
    )

    # 6c. Split conformal prediction: kapsama-garantili tahmin kümeleri
    #     (held-out'ta yalnızca raporlama; kural/kod tuning yapılmaz).
    from src.utils.konformal import konformal_degerlendirme
    konformal = konformal_degerlendirme(kalibre_olasiliklar, gercek_tur, alfa=0.1)

    # 7. Özet kalitesi (referanssız: sadakat / kaynak-kapsama / sıkıştırma)
    from src.utils.ozet_kalite import kaynak_kapsama, sadakat, sikistirma_orani
    sad_l: List[float] = []
    kap_l: List[float] = []
    sik_l: List[float] = []
    for s in sonuclar:
        kaynak = s.get("kaynak_metin", "")
        ozet = s.get("tahmin_ozet", "")
        if not kaynak:
            continue
        sad_l.append(sadakat(ozet, kaynak))
        kap = kaynak_kapsama(ozet, kaynak)
        if kap is not None:
            kap_l.append(kap)
        sik_l.append(sikistirma_orani(ozet, kaynak))

    def _ort(xs: List[float]) -> Optional[float]:
        return round(sum(xs) / len(xs), 4) if xs else None

    ozet_kalitesi = {
        "n": len(sad_l),
        "sadakat": _ort(sad_l),
        "kaynak_kapsama": _ort(kap_l),
        "sikistirma_orani": _ort(sik_l),
    }

    return {
        "zaman_damgasi": datetime.now().isoformat(timespec="seconds"),
        "veri_dizini": goreli_yol(veri_dizini),
        "set_adi": Path(veri_dizini).name,
        "llm": llm_bilgisi_al(),
        "degerlendirilen_dosya_sayisi": len(sonuclar),
        "siniflandirma": {
            "accuracy": round(hesapla_accuracy(gercek_tur, tahmin_tur), 4),
            "macro_f1": sinif_metrikleri["macro_f1"],
            "macro_precision": sinif_metrikleri["macro_precision"],
            "macro_recall": sinif_metrikleri["macro_recall"],
            "sinif_bazinda": sinif_metrikleri["sinif_bazinda"],
            "confusion_matrix": hesapla_confusion_matrix(gercek_tur, tahmin_tur),
            "yanlis_siniflananlar": hesapla_yanlis_listesi(
                dosyalar, gercek_tur, tahmin_tur
            ),
        },
        "yonlendirme": {
            "accuracy": round(hesapla_accuracy(gercek_birim, tahmin_birim), 4),
            "yanlis_yonlendirilenler": hesapla_yanlis_listesi(
                dosyalar, gercek_birim, tahmin_birim
            ),
        },
        "eksik_bilgi_tespiti": hesapla_set_metrikleri(eksik_ciftler),
        "mevzuat_onerisi": {
            "isabet_at_3": hesapla_isabet_at_k(mevzuat_ciftler, k=3),
            "isabet_at_1": hesapla_isabet_at_k(mevzuat_ciftler, k=1),
            "siralama": hesapla_siralama_metrikleri(mevzuat_ciftler, k=3),
            "isabetsizler": hesapla_isabet_kacaklari(
                dosyalar, beklenen_mevzuat, tahmin_mevzuat, k=3
            ),
        },
        "taslak_kalitesi": hesapla_taslak_kalitesi(sonuclar),
        "kalibrasyon": kalibrasyon,
        "secici_tahmin": secici_tahmin,
        "konformal": konformal,
        "ozet_kalitesi": ozet_kalitesi,
        "performans": {
            "evrak_basina_ortalama_sure_saniye": ortalama_sure,
            "evrak_basina_medyan_sure_saniye": round(hesapla_medyan(sureler), 4),
            "adim_bazinda_ortalama_sure_saniye": hesapla_adim_ortalamalari(
                [s["adimlar"] for s in sonuclar]
            ),
        },
        "islenemeyen_dosyalar": islenemeyenler,
    }


# ---------------------------------------------------------------------------
# RAPORLAMA
# ---------------------------------------------------------------------------

def konsol_raporu_yazdir(rapor: Dict[str, Any]) -> None:
    """Metrikleri rich Table'larla konsola yazdırır."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    llm = rapor["llm"]
    console.print(
        "\n[bold]Kamu Evrak Akıllı Ajan — Değerlendirme Raporu[/bold]\n"
        f"Zaman: {rapor['zaman_damgasi']}  |  "
        f"Set: {rapor.get('set_adi', '?')}  |  "
        f"LLM backend: {llm['backend']} "
        f"({'aktif' if llm['kullanilabilir'] else 'offline — kural tabanlı mod'})  |  "
        f"Dosya sayısı: {rapor['degerlendirilen_dosya_sayisi']}\n"
    )

    # 1. Sınıflandırma tablosu
    sinif = rapor["siniflandirma"]
    tablo = Table(title="1. Evrak Sınıflandırma Başarımı")
    tablo.add_column("Tür", style="cyan")
    tablo.add_column("Precision", justify="right")
    tablo.add_column("Recall", justify="right")
    tablo.add_column("F1", justify="right")
    tablo.add_column("Destek", justify="right")
    for tur, m in sinif["sinif_bazinda"].items():
        tablo.add_row(
            tur, f"{m['precision']:.3f}", f"{m['recall']:.3f}",
            f"{m['f1']:.3f}", str(m["destek"]),
        )
    tablo.add_row(
        "[bold]MACRO / ACC[/bold]",
        f"[bold]{sinif['macro_precision']:.3f}[/bold]",
        f"[bold]{sinif['macro_recall']:.3f}[/bold]",
        f"[bold]{sinif['macro_f1']:.3f}[/bold]",
        f"[bold]acc={sinif['accuracy']:.3f}[/bold]",
    )
    console.print(tablo)

    if sinif["yanlis_siniflananlar"]:
        yanlis = Table(title="Yanlış Sınıflananlar (confusion özeti)")
        yanlis.add_column("Dosya", style="yellow")
        yanlis.add_column("Beklenen")
        yanlis.add_column("Tahmin", style="red")
        for y in sinif["yanlis_siniflananlar"]:
            yanlis.add_row(y["dosya"], y["beklenen"], y["tahmin"])
        console.print(yanlis)

    # 2. Yönlendirme tablosu
    yon = rapor["yonlendirme"]
    tablo2 = Table(title="2. Birim Yönlendirme Başarımı")
    tablo2.add_column("Metrik", style="cyan")
    tablo2.add_column("Değer", justify="right")
    tablo2.add_row("Accuracy", f"{yon['accuracy']:.3f}")
    tablo2.add_row("Yanlış yönlendirme", str(len(yon["yanlis_yonlendirilenler"])))
    console.print(tablo2)

    if yon["yanlis_yonlendirilenler"]:
        yanlis2 = Table(title="Yanlış Yönlendirilenler")
        yanlis2.add_column("Dosya", style="yellow")
        yanlis2.add_column("Beklenen birim")
        yanlis2.add_column("Tahmin", style="red")
        for y in yon["yanlis_yonlendirilenler"]:
            yanlis2.add_row(y["dosya"], y["beklenen"], y["tahmin"])
        console.print(yanlis2)

    # 3. Eksik bilgi tespiti tablosu
    eksik = rapor["eksik_bilgi_tespiti"]
    tablo3 = Table(title="3. Eksik Bilgi Tespiti (alan bazında, micro)")
    tablo3.add_column("Metrik", style="cyan")
    tablo3.add_column("Değer", justify="right")
    tablo3.add_row("Micro Precision", f"{eksik['micro_precision']:.3f}")
    tablo3.add_row("Micro Recall", f"{eksik['micro_recall']:.3f}")
    tablo3.add_row("Micro F1", f"{eksik['micro_f1']:.3f}")
    tablo3.add_row("TP / FP / FN", f"{eksik['tp']} / {eksik['fp']} / {eksik['fn']}")
    console.print(tablo3)

    # 4. Mevzuat önerisi tablosu (isabet@k)
    mevzuat = rapor.get("mevzuat_onerisi") or {}
    if mevzuat:
        at3 = mevzuat.get("isabet_at_3", {})
        at1 = mevzuat.get("isabet_at_1", {})
        tablo_m = Table(title="4. Mevzuat Önerisi Başarımı (isabet@k)")
        tablo_m.add_column("Metrik", style="cyan")
        tablo_m.add_column("Değer", justify="right")
        oran3 = at3.get("isabet_orani")
        oran1 = at1.get("isabet_orani")
        tablo_m.add_row(
            "isabet@3", f"{oran3:.3f}" if oran3 is not None else "etiket yok"
        )
        tablo_m.add_row(
            "isabet@1", f"{oran1:.3f}" if oran1 is not None else "etiket yok"
        )
        tablo_m.add_row("Etiketli evrak", str(at3.get("etiketli_evrak", 0)))
        tablo_m.add_row("Kaçırılan (@3)", str(len(mevzuat.get("isabetsizler", []))))
        console.print(tablo_m)

        if mevzuat.get("isabetsizler"):
            yanlis_m = Table(title="Mevzuat İsabetsizleri (@3)")
            yanlis_m.add_column("Dosya", style="yellow")
            yanlis_m.add_column("Beklenen")
            yanlis_m.add_column("İlk 3 tahmin", style="red")
            for y in mevzuat["isabetsizler"]:
                yanlis_m.add_row(
                    y["dosya"], ", ".join(y["beklenen"]), ", ".join(y["tahmin"])
                )
            console.print(yanlis_m)

    # 5. Taslak kalitesi tablosu (bağımsız hakem, 0-100)
    kalite = rapor.get("taslak_kalitesi") or {}
    if kalite.get("degerlendirilen"):
        tablo_k = Table(title="5. Taslak Kalitesi (bağımsız hakem, 0-100)")
        tablo_k.add_column("Metrik", style="cyan")
        tablo_k.add_column("Değer", justify="right")
        tablo_k.add_row("Ortalama puan", f"{kalite['ortalama_puan']:.1f}")
        tablo_k.add_row("Asgari puan", f"{kalite['asgari_puan']:.1f}")
        tablo_k.add_row("Değerlendirilen taslak", str(kalite["degerlendirilen"]))
        tablo_k.add_row(
            "Hakem yöntemi",
            ", ".join(f"{y}: {n}" for y, n in kalite.get("yontemler", {}).items()),
        )
        console.print(tablo_k)

    # 6. Performans tablosu
    perf = rapor["performans"]
    tablo4 = Table(title="6. Performans (gerçek zamana yakınlık)")
    tablo4.add_column("Adım / Metrik", style="cyan")
    tablo4.add_column("Süre (sn)", justify="right")
    tablo4.add_row(
        "[bold]Evrak başına ortalama[/bold]",
        f"[bold]{perf['evrak_basina_ortalama_sure_saniye']:.3f}[/bold]",
    )
    tablo4.add_row(
        "[bold]Evrak başına medyan[/bold]",
        f"[bold]{perf['evrak_basina_medyan_sure_saniye']:.3f}[/bold]",
    )
    for agent, sure in perf["adim_bazinda_ortalama_sure_saniye"].items():
        tablo4.add_row(f"  {agent}", f"{sure:.4f}")
    console.print(tablo4)

    if rapor["islenemeyen_dosyalar"]:
        tablo5 = Table(title="İşlenemeyen Dosyalar")
        tablo5.add_column("Dosya", style="yellow")
        tablo5.add_column("Hata", style="red")
        for h in rapor["islenemeyen_dosyalar"]:
            tablo5.add_row(h["dosya"], h["hata"])
        console.print(tablo5)


def raporu_kaydet(rapor: Dict[str, Any], rapor_yolu: Path) -> None:
    """Raporu JSON dosyası olarak kaydeder."""
    rapor_yolu.parent.mkdir(parents=True, exist_ok=True)
    with open(rapor_yolu, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    logger.info(f"Rapor kaydedildi: {rapor_yolu}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """CLI giriş noktası."""
    parser = argparse.ArgumentParser(
        description=(
            "Kamu Evrak Akıllı Ajan değerlendirme aracı — etiketli kurgu "
            "evraklar üzerinde sınıflandırma, yönlendirme, eksik bilgi "
            "tespiti ve performans metrikleri üretir."
        )
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Sadece ilk N etiketli dosyayı değerlendir",
    )
    parser.add_argument(
        "--dosya", type=str, default=None, metavar="DOSYA",
        help="Sadece belirtilen tek dosyayı değerlendir (etiketler.json içindeki ad)",
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="Konsol tablolarını atla; raporu sadece JSON olarak stdout'a yaz",
    )
    parser.add_argument(
        "--veri-dizini", type=str, default=str(EVRAK_DIZINI), metavar="DIZIN",
        help=(
            "İçinde etiketler.json ve .txt evrakları bulunan veri dizini "
            "(varsayılan: geliştirme seti data/raw/kurgu_evraklar; held-out "
            "ölçümü için data/raw/kurgu_evraklar_heldout verin)"
        ),
    )
    parser.add_argument(
        "--rapor-dosyasi", type=str, default=str(RAPOR_DOSYASI), metavar="DOSYA",
        help=(
            "JSON raporunun yazılacağı dosya yolu "
            "(varsayılan: data/processed/eval_report.json)"
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.json_only else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    veri_dizini = Path(args.veri_dizini)
    rapor_dosyasi = Path(args.rapor_dosyasi)

    etiketler = etiketleri_yukle(veri_dizini / "etiketler.json")
    sonuclar, islenemeyenler = evraklari_isle(
        etiketler, limit=args.limit, tek_dosya=args.dosya,
        evrak_dizini=veri_dizini,
    )

    if not sonuclar:
        print("HATA: Hiçbir dosya işlenemedi — metrik hesaplanamıyor.", file=sys.stderr)
        for h in islenemeyenler:
            print(f"  - {h['dosya']}: {h['hata']}", file=sys.stderr)
        return 1

    rapor = metrikleri_hesapla(sonuclar, islenemeyenler, veri_dizini=veri_dizini)
    raporu_kaydet(rapor, rapor_dosyasi)

    if args.json_only:
        print(json.dumps(rapor, ensure_ascii=False, indent=2))
    else:
        konsol_raporu_yazdir(rapor)
        print(f"\nJSON raporu: {rapor_dosyasi}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
