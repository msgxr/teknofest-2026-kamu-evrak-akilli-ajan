"""
Performans/Ölçeklenebilirlik Benchmark Aracı.

Şartname Referansı:
    "Gerçek zamana yakın çalışma avantaj sağlayacaktır." — bu araç,
    'gerçek zamana yakın' iddiasını ölçülmüş sayılara bağlar:
    evrak/saniye (throughput), gecikme yüzdelikleri, adım bazında süre
    dağılımı, tepe bellek ve soğuk başlangıç süresi.

Yöntem (neden böyle ölçüyoruz):
    1. Soğuk başlangıç AYRI ölçülür: pipeline modül importu + kurulum
       (agent yükleme) süresi ile ilk evrak işleme (ısınma: tembel
       import/regex derleme) süresi ayrı raporlanır; bunlar tekrarlanan
       ölçümlere KARIŞTIRILMAZ — aksi hâlde p99 yapay şişerdi.
    2. Gecikme ölçümü: 3 etiketli setin tüm evrakları --tekrar N kez
       (varsayılan 5) işlenir; her evrak işleme çağrısı time.perf_counter
       ile duvar saati üzerinden ölçülür. Yüzdelikler (p95/p99) tekil
       yavaş evrakları ortalamanın gizlemesini önler.
    3. Bellek ölçümü AYRI bir turda yapılır: tracemalloc izleme ek yük
       getirdiği için gecikme ölçümüyle aynı turda çalıştırılmaz;
       tepe (peak) Python tahsisi raporlanır.
    4. Ölçekleme testi: aynı evrak kümesi bellek içinde 1x/5x/10x
       çoğaltılıp toplam süre ölçülür. Evrak başına süre ölçekle sabit
       kalıyorsa (doğrusallık oranı ≈ 1.0) sistem evrak sayısında
       doğrusal ölçeklenir — durum sızıntısı/birikim yoktur.
    5. Rastgelelik YOKTUR: set sırası sabittir, dosyalar ad sırasıyla
       işlenir; aynı makinede tekrar çalıştırma karşılaştırılabilir
       sonuç verir.

Not: Ölçüm KURAL-TABANLI (offline) mod içindir; bir LLM backend'i
aktifse sonuçlar LLM gecikmesini içerir ve araç bunu başta uyarır.

Çıktılar:
    - Konsol raporu (rich Table)
    - data/processed/benchmark_raporu.json (zaman damgası + makine bilgisi)

Kullanım:
    python3 scripts/benchmark.py                 # varsayılan: 5 tekrar
    python3 scripts/benchmark.py --tekrar 3      # 3 tekrar
    python3 scripts/benchmark.py --json-only     # tablo yok, sadece JSON

Metrik fonksiyonları saf Python'dur ve pipeline çalıştırılmadan import
edilebilir — birim testleri bunları doğrudan test eder
(tests/test_benchmark.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Proje kökünü sys.path'e ekle (script doğrudan çalıştırıldığında gerekli)
PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

logger = logging.getLogger("kamu_evrak_ajan.benchmark")

# Değerlendirme setleri: sabit sırada işlenir (deterministik ölçüm).
# 35 (geliştirme) + 16 (held-out) + 16 (held-out v2) = 67 evrak.
SET_DIZINLERI = [
    PROJE_KOKU / "data" / "raw" / "kurgu_evraklar",
    PROJE_KOKU / "data" / "raw" / "kurgu_evraklar_heldout",
    PROJE_KOKU / "data" / "raw" / "kurgu_evraklar_heldout_v2",
]

RAPOR_DOSYASI = PROJE_KOKU / "data" / "processed" / "benchmark_raporu.json"

# Ölçekleme testi çarpanları: 1x taban, 5x/10x orta ve yüksek yük.
OLCEK_CARPANLARI = [1, 5, 10]


def goreli_yol(yol: Any) -> str:
    """
    Yolu proje köküne göre göreli dizeye çevirir.

    # GÜVENLİK: rapor JSON'u git ile izlenebilir; mutlak yol
    # (makine/kullanıcı adı) sızmaması için yol köke göre göreli yazılır,
    # kök dışındaki yollar için yalnızca dosya adı raporlanır.
    """
    p = Path(yol).resolve()
    try:
        return p.relative_to(PROJE_KOKU).as_posix()
    except ValueError:
        return p.name


# ---------------------------------------------------------------------------
# SAF METRİK FONKSİYONLARI (pipeline'dan bağımsız, birim testlenebilir)
# ---------------------------------------------------------------------------

def hesapla_yuzdelik(degerler: Sequence[float], yuzde: float) -> float:
    """
    Sıralı istatistikte doğrusal enterpolasyonla yüzdelik hesaplar.

    Yöntem: sıralanmış n değerde konum = (n-1) * yuzde/100; konum tam
    sayı değilse komşu iki değer arasında doğrusal enterpolasyon yapılır
    (numpy'nin varsayılan 'linear' yöntemiyle aynı tanım — sklearn/numpy
    kullanılmadan saf Python ile).

    Args:
        degerler: Ölçüm değerleri (sıralı olması gerekmez)
        yuzde: İstenen yüzdelik (0–100)

    Returns:
        Yüzdelik değeri (boş girişte 0.0)
    """
    if not degerler:
        return 0.0
    sirali = sorted(degerler)
    if len(sirali) == 1:
        return float(sirali[0])
    yuzde = min(max(yuzde, 0.0), 100.0)
    konum = (len(sirali) - 1) * (yuzde / 100.0)
    alt = int(konum)
    ust = min(alt + 1, len(sirali) - 1)
    kesir = konum - alt
    return float(sirali[alt] + (sirali[ust] - sirali[alt]) * kesir)


def hesapla_gecikme_istatistikleri(sureler: Sequence[float]) -> Dict[str, float]:
    """
    Gecikme ölçümlerinden özet istatistik üretir.

    Ortalama tek başına yanıltıcıdır (tekil yavaş evrakları gizler);
    bu yüzden medyan ve kuyruk yüzdelikleri (p95/p99) birlikte verilir —
    'gerçek zamana yakın' iddiası kuyruk gecikmesiyle kanıtlanır.

    Args:
        sureler: Evrak başına işlem süreleri (saniye)

    Returns:
        {"ortalama", "medyan", "p95", "p99", "min", "max", "olcum_sayisi"}
        (boş girişte tüm değerler 0.0)
    """
    if not sureler:
        return {
            "ortalama": 0.0, "medyan": 0.0, "p95": 0.0, "p99": 0.0,
            "min": 0.0, "max": 0.0, "olcum_sayisi": 0,
        }
    return {
        "ortalama": sum(sureler) / len(sureler),
        "medyan": hesapla_yuzdelik(sureler, 50),
        "p95": hesapla_yuzdelik(sureler, 95),
        "p99": hesapla_yuzdelik(sureler, 99),
        "min": float(min(sureler)),
        "max": float(max(sureler)),
        "olcum_sayisi": len(sureler),
    }


def hesapla_throughput(evrak_sayisi: int, toplam_sure_saniye: float) -> float:
    """
    İş hacmini (evrak/saniye) hesaplar.

    Args:
        evrak_sayisi: İşlenen toplam evrak sayısı
        toplam_sure_saniye: Toplam duvar saati süresi (saniye)

    Returns:
        Evrak/saniye (süre veya sayı pozitif değilse 0.0 — sıfıra bölme yok)
    """
    if evrak_sayisi <= 0 or toplam_sure_saniye <= 0:
        return 0.0
    return evrak_sayisi / toplam_sure_saniye


def hesapla_adim_dagilimi(
    adim_kayitlari: Sequence[Sequence[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Çok sayıda çalıştırmanın işlem adımı kayıtlarından adım bazında
    ortalama süre ve toplam içindeki payı hesaplar.

    Yalnızca "success" durumundaki adımlar süre ortalamasına katılır
    (atlanmış adımların 0.0 süresi ortalamayı yapay düşürmesin diye);
    adım sırası pipeline'daki ilk görülme sırasıyla korunur.

    Args:
        adim_kayitlari: Her çalıştırma için islem_adimlari listesi
            ([{"agent", "status", "sure_saniye", ...}, ...])

    Returns:
        [{"agent", "calisma_sayisi", "ortalama_saniye", "pay_yuzde"}, ...]
    """
    toplamlar: Dict[str, float] = {}
    sayilar: Dict[str, int] = {}
    sira: List[str] = []
    for kayit in adim_kayitlari:
        for adim in kayit:
            agent = adim.get("agent", "?")
            if agent not in toplamlar:
                toplamlar[agent] = 0.0
                sayilar[agent] = 0
                sira.append(agent)
            if adim.get("status") == "success":
                toplamlar[agent] += float(adim.get("sure_saniye", 0.0))
                sayilar[agent] += 1

    genel_toplam = sum(toplamlar.values())
    dagilim = []
    for agent in sira:
        adet = sayilar[agent]
        dagilim.append({
            "agent": agent,
            "calisma_sayisi": adet,
            "ortalama_saniye": (toplamlar[agent] / adet) if adet else 0.0,
            "pay_yuzde": (
                100.0 * toplamlar[agent] / genel_toplam if genel_toplam > 0 else 0.0
            ),
        })
    return dagilim


def hesapla_dogrusallik(olcumler: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ölçekleme ölçümlerine evrak başına süre ve doğrusallık oranı ekler.

    Doğrusallık oranı = (k ölçeğindeki evrak başına süre) /
    (1x ölçeğindeki evrak başına süre). Oran ≈ 1.0 ise sistem evrak
    sayısında doğrusal ölçeklenir (yük büyüdükçe evrak başına maliyet
    sabit kalır); oran > 1 birikim/durum sızıntısına işaret eder.

    Args:
        olcumler: [{"olcek", "evrak_sayisi", "toplam_sure_saniye"}, ...]
            (ilk öğe 1x taban ölçümü olmalıdır)

    Returns:
        Girdinin kopyası + "evrak_basina_saniye" ve "dogrusallik_orani"
        alanları (taban süresi 0 ise oran 0.0)
    """
    sonuclar: List[Dict[str, Any]] = []
    taban_birim = 0.0
    for i, olcum in enumerate(olcumler):
        adet = int(olcum.get("evrak_sayisi", 0))
        toplam = float(olcum.get("toplam_sure_saniye", 0.0))
        birim = (toplam / adet) if adet > 0 else 0.0
        if i == 0:
            taban_birim = birim
        kayit = dict(olcum)
        kayit["evrak_basina_saniye"] = birim
        kayit["dogrusallik_orani"] = (birim / taban_birim) if taban_birim > 0 else 0.0
        sonuclar.append(kayit)
    return sonuclar


# ---------------------------------------------------------------------------
# EVRAK YÜKLEME
# ---------------------------------------------------------------------------

def evraklari_yukle(set_dizinleri: Sequence[Path]) -> List[Dict[str, str]]:
    """
    Değerlendirme setlerindeki evrak dosyalarını deterministik sırayla yükler.

    Her set içinde dosyalar ad sırasına göre işlenir; set sırası sabittir.
    Metinler ölçekleme testi için belleğe alınır (etiketler.json evrak
    değildir, yüklenmez).

    Returns:
        [{"yol": str, "ad": str, "metin": str}, ...]
    """
    evraklar: List[Dict[str, str]] = []
    for dizin in set_dizinleri:
        if not dizin.is_dir():
            logger.warning(f"Set dizini bulunamadı, atlanıyor: {dizin}")
            continue
        for dosya in sorted(dizin.glob("*.txt")):
            evraklar.append({
                "yol": str(dosya),
                "ad": f"{dizin.name}/{dosya.name}",
                "metin": dosya.read_text(encoding="utf-8"),
            })
    return evraklar


# ---------------------------------------------------------------------------
# BENCHMARK AKIŞI
# ---------------------------------------------------------------------------

def llm_durumunu_bildir() -> str:
    """
    LLM backend durumunu tespit eder ve kullanıcıyı bilgilendirir.

    Ölçüm kural-tabanlı (offline) mod içindir; LLM aktifse sonuçlar
    LLM gecikmesini içereceğinden karşılaştırılamaz — bu açıkça uyarılır.

    Returns:
        Tespit edilen backend adı ("offline", "openai", "ollama", ...)
    """
    try:
        from src.models.llm_wrapper import get_default_llm

        backend = get_default_llm().backend
    except Exception as exc:  # LLM katmanı hiç yüklenemezse offline say
        logger.warning(f"LLM backend tespiti yapılamadı: {exc}")
        backend = "offline"

    if backend == "offline":
        print(
            "[BİLGİ] LLM backend'i: offline — ölçüm KURAL-TABANLI mod "
            "içindir (hedeflenen ölçüm modu budur)."
        )
    else:
        print(
            f"[UYARI] LLM backend'i aktif ({backend}) — sonuçlar LLM "
            "gecikmesini içerir; kural-tabanlı mod ölçümü için LLM'i "
            "devre dışı bırakın."
        )
    return backend


def benchmark_calistir(tekrar: int) -> Dict[str, Any]:
    """
    Benchmark'ı uçtan uca çalıştırır ve tüm metrikleri döndürür.

    Adımlar: (1) soğuk başlangıç (import + pipeline kurulumu),
    (2) ısınma (ilk evrak), (3) gecikme turları (tekrar × evrak),
    (4) bellek turu (tracemalloc ile ayrı), (5) ölçekleme (1x/5x/10x).

    Args:
        tekrar: Gecikme ölçümünde her evrakın kaç kez işleneceği

    Returns:
        Rapor sözlüğü (JSON'a yazılabilir)
    """
    backend = llm_durumunu_bildir()

    evraklar = evraklari_yukle(SET_DIZINLERI)
    if not evraklar:
        raise SystemExit("Hiç evrak bulunamadı; data/raw altındaki setleri kontrol edin.")
    print(f"[BİLGİ] {len(evraklar)} evrak yüklendi ({len(SET_DIZINLERI)} set).")

    # --- 1) Soğuk başlangıç: modül importu + pipeline kurulumu -------------
    t0 = time.perf_counter()
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    pipeline = EndToEndPipeline(kayit_defteri_aktif=False)
    soguk_baslangic = time.perf_counter() - t0

    # --- 2) Isınma: ilk evrak (tembel import/regex derleme buraya düşer) ---
    # Bu süre tekrarlı ölçümlere katılmaz; katılsaydı p99 yapay şişerdi.
    t0 = time.perf_counter()
    pipeline.process(evraklar[0]["yol"], kayit=False)
    isinma_suresi = time.perf_counter() - t0

    # --- 3) Gecikme turları: tekrar × evrak -------------------------------
    print(f"[BİLGİ] Gecikme ölçümü: {len(evraklar)} evrak × {tekrar} tekrar...")
    gecikmeler: List[float] = []
    adim_kayitlari: List[List[Dict[str, Any]]] = []
    tur_baslangic = time.perf_counter()
    for _ in range(tekrar):
        for evrak in evraklar:
            t = time.perf_counter()
            sonuc = pipeline.process(evrak["yol"], kayit=False)
            gecikmeler.append(time.perf_counter() - t)
            adim_kayitlari.append(sonuc.get("islem_adimlari", []))
    toplam_sure = time.perf_counter() - tur_baslangic

    gecikme = hesapla_gecikme_istatistikleri(gecikmeler)
    throughput = hesapla_throughput(len(gecikmeler), toplam_sure)
    adim_dagilimi = hesapla_adim_dagilimi(adim_kayitlari)

    # --- 4) Bellek turu: tracemalloc ek yükü gecikmeyi bozmasın diye ayrı --
    print("[BİLGİ] Bellek ölçümü (tracemalloc, 1 tur)...")
    tracemalloc.start()
    for evrak in evraklar:
        pipeline.process(evrak["yol"], kayit=False)
    _, tepe_bayt = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # --- 5) Ölçekleme: bellek içi 1x/5x/10x --------------------------------
    olcek_olcumleri: List[Dict[str, Any]] = []
    for carpan in OLCEK_CARPANLARI:
        kume = evraklar * carpan
        print(f"[BİLGİ] Ölçekleme testi: {carpan}x ({len(kume)} evrak)...")
        t = time.perf_counter()
        for evrak in kume:
            pipeline.process_text(evrak["metin"], source_name=evrak["ad"], kayit=False)
        olcek_olcumleri.append({
            "olcek": carpan,
            "evrak_sayisi": len(kume),
            "toplam_sure_saniye": round(time.perf_counter() - t, 3),
        })
    olcekleme = hesapla_dogrusallik(olcek_olcumleri)

    return {
        "zaman_damgasi": datetime.now().isoformat(timespec="seconds"),
        "makine": {
            "isletim_sistemi": platform.system(),
            "surum": platform.release(),
            "mimari": platform.machine(),
            "islemci": platform.processor(),
            "cekirdek_sayisi": os.cpu_count(),
            "python_surumu": platform.python_version(),
        },
        "llm_backend": backend,
        "yapilandirma": {
            "tekrar": tekrar,
            "evrak_sayisi": len(evraklar),
            "setler": [goreli_yol(d) for d in SET_DIZINLERI if d.is_dir()],
            "olcek_carpanlari": OLCEK_CARPANLARI,
        },
        "soguk_baslangic": {
            "pipeline_kurulum_saniye": round(soguk_baslangic, 3),
            "ilk_evrak_isinma_saniye": round(isinma_suresi, 3),
        },
        "gecikme_ms": {
            "ortalama": round(gecikme["ortalama"] * 1000, 2),
            "medyan": round(gecikme["medyan"] * 1000, 2),
            "p95": round(gecikme["p95"] * 1000, 2),
            "p99": round(gecikme["p99"] * 1000, 2),
            "min": round(gecikme["min"] * 1000, 2),
            "max": round(gecikme["max"] * 1000, 2),
            "olcum_sayisi": gecikme["olcum_sayisi"],
        },
        "throughput": {
            "evrak_bolu_saniye": round(throughput, 1),
            "toplam_evrak": len(gecikmeler),
            "toplam_sure_saniye": round(toplam_sure, 3),
        },
        "adim_dagilimi": [
            {
                "agent": a["agent"],
                "calisma_sayisi": a["calisma_sayisi"],
                "ortalama_ms": round(a["ortalama_saniye"] * 1000, 2),
                "pay_yuzde": round(a["pay_yuzde"], 1),
            }
            for a in adim_dagilimi
        ],
        "bellek": {
            "tepe_mb": round(tepe_bayt / (1024 * 1024), 2),
            "yontem": "tracemalloc (Python tahsisleri, ayrı turda ölçüldü)",
        },
        "olcekleme": [
            {
                "olcek": o["olcek"],
                "evrak_sayisi": o["evrak_sayisi"],
                "toplam_sure_saniye": o["toplam_sure_saniye"],
                "evrak_basina_ms": round(o["evrak_basina_saniye"] * 1000, 2),
                "dogrusallik_orani": round(o["dogrusallik_orani"], 2),
            }
            for o in olcekleme
        ],
    }


# ---------------------------------------------------------------------------
# RAPORLAMA
# ---------------------------------------------------------------------------

def konsola_yazdir(rapor: Dict[str, Any]) -> None:
    """Benchmark raporunu rich tablolarıyla konsola yazdırır."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    makine = rapor["makine"]
    console.print(
        f"\n[bold]Performans Benchmark Raporu[/bold] — {rapor['zaman_damgasi']}\n"
        f"Makine: {makine['isletim_sistemi']} {makine['surum']} / "
        f"{makine['mimari']} / {makine['cekirdek_sayisi']} çekirdek / "
        f"Python {makine['python_surumu']} — LLM: {rapor['llm_backend']}"
    )

    ozet = Table(title="Genel Özet")
    ozet.add_column("Metrik", style="cyan")
    ozet.add_column("Değer", justify="right")
    sb = rapor["soguk_baslangic"]
    g = rapor["gecikme_ms"]
    t = rapor["throughput"]
    ozet.add_row("Soğuk başlangıç (pipeline kurulumu)", f"{sb['pipeline_kurulum_saniye']} sn")
    ozet.add_row("Isınma (ilk evrak)", f"{sb['ilk_evrak_isinma_saniye']} sn")
    ozet.add_row("Throughput", f"{t['evrak_bolu_saniye']} evrak/sn")
    ozet.add_row("Toplam ölçüm", f"{t['toplam_evrak']} evrak / {t['toplam_sure_saniye']} sn")
    ozet.add_row("Gecikme ortalama", f"{g['ortalama']} ms")
    ozet.add_row("Gecikme medyan", f"{g['medyan']} ms")
    ozet.add_row("Gecikme p95", f"{g['p95']} ms")
    ozet.add_row("Gecikme p99", f"{g['p99']} ms")
    ozet.add_row("Gecikme min–max", f"{g['min']}–{g['max']} ms")
    ozet.add_row("Tepe bellek (tracemalloc)", f"{rapor['bellek']['tepe_mb']} MB")
    console.print(ozet)

    adimlar = Table(title="Adım Bazında Ortalama Süre")
    adimlar.add_column("Agent", style="cyan")
    adimlar.add_column("Çalışma", justify="right")
    adimlar.add_column("Ortalama (ms)", justify="right")
    adimlar.add_column("Pay (%)", justify="right")
    for a in rapor["adim_dagilimi"]:
        adimlar.add_row(
            a["agent"], str(a["calisma_sayisi"]),
            f"{a['ortalama_ms']}", f"{a['pay_yuzde']}",
        )
    console.print(adimlar)

    olcek = Table(title="Ölçekleme Testi (bellek içi çoğaltma)")
    olcek.add_column("Ölçek", justify="right")
    olcek.add_column("Evrak", justify="right")
    olcek.add_column("Toplam (sn)", justify="right")
    olcek.add_column("Evrak başına (ms)", justify="right")
    olcek.add_column("Doğrusallık oranı", justify="right")
    for o in rapor["olcekleme"]:
        olcek.add_row(
            f"{o['olcek']}x", str(o["evrak_sayisi"]),
            f"{o['toplam_sure_saniye']}", f"{o['evrak_basina_ms']}",
            f"{o['dogrusallik_orani']}",
        )
    console.print(olcek)


def main() -> None:
    """CLI giriş noktası."""
    parser = argparse.ArgumentParser(
        description="Kamu Evrak Akıllı Ajan — performans/ölçeklenebilirlik benchmark'ı"
    )
    parser.add_argument(
        "--tekrar", type=int, default=5,
        help="Gecikme ölçümünde her evrakın kaç kez işleneceği (varsayılan: 5)",
    )
    parser.add_argument(
        "--rapor-dosyasi", type=Path, default=RAPOR_DOSYASI,
        help="JSON rapor çıktı yolu (varsayılan: data/processed/benchmark_raporu.json)",
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="Konsol tablolarını basma; yalnızca JSON raporu yaz",
    )
    args = parser.parse_args()
    if args.tekrar < 1:
        parser.error("--tekrar en az 1 olmalıdır")

    # Pipeline INFO logları ölçüm çıktısını boğar; uyarı ve üstü yeter.
    logging.basicConfig(level=logging.WARNING)

    rapor = benchmark_calistir(args.tekrar)

    args.rapor_dosyasi.parent.mkdir(parents=True, exist_ok=True)
    args.rapor_dosyasi.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[BİLGİ] JSON rapor yazıldı: {goreli_yol(args.rapor_dosyasi)}")

    if not args.json_only:
        konsola_yazdir(rapor)


if __name__ == "__main__":
    main()
