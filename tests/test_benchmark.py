"""
Benchmark Aracı metrik fonksiyonlarının birim testleri.

scripts/benchmark.py içindeki saf metrik fonksiyonlarını (yüzdelik,
gecikme istatistikleri, throughput, adım dağılımı, doğrusallık oranı)
pipeline ÇALIŞTIRMADAN, küçük sabit örneklerle test eder.

Şartname Referansı:
    "Gerçek zamana yakın çalışma avantaj sağlayacaktır." — performans
    iddiasını sayıya bağlayan metriklerin doğru hesaplandığının kanıtı.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.benchmark import (
    goreli_yol,
    hesapla_adim_dagilimi,
    hesapla_dogrusallik,
    hesapla_gecikme_istatistikleri,
    hesapla_throughput,
    hesapla_yuzdelik,
)


class TestYuzdelik:
    """hesapla_yuzdelik birim testleri (doğrusal enterpolasyon)."""

    def test_bos_giris(self):
        """Boş giriş 0.0 döndürmeli (istisna fırlatmamalı)."""
        assert hesapla_yuzdelik([], 95) == 0.0

    def test_tek_deger(self):
        """Tek değerde her yüzdelik o değerin kendisidir."""
        assert hesapla_yuzdelik([7.5], 0) == 7.5
        assert hesapla_yuzdelik([7.5], 50) == 7.5
        assert hesapla_yuzdelik([7.5], 99) == 7.5

    def test_medyan_cift_eleman(self):
        """Çift elemanda medyan iki orta değerin ortalamasıdır."""
        assert hesapla_yuzdelik([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)

    def test_medyan_tek_eleman_sayisi(self):
        """Tek sayıda elemanda medyan orta değerdir."""
        assert hesapla_yuzdelik([3.0, 1.0, 2.0], 50) == pytest.approx(2.0)

    def test_uc_degerler(self):
        """p0 en küçük, p100 en büyük değeri vermeli."""
        degerler = [5.0, 1.0, 3.0]
        assert hesapla_yuzdelik(degerler, 0) == 1.0
        assert hesapla_yuzdelik(degerler, 100) == 5.0

    def test_enterpolasyon(self):
        """1..100 dizisinde p95, 95 ile 96 arasında enterpole edilmeli."""
        degerler = [float(i) for i in range(1, 101)]
        # konum = 99 * 0.95 = 94.05 → 95 + 0.05*(96-95) = 95.05
        assert hesapla_yuzdelik(degerler, 95) == pytest.approx(95.05)

    def test_sirasiz_giris(self):
        """Giriş sırasız olsa da sonuç sıralı veri üzerinden hesaplanmalı."""
        assert hesapla_yuzdelik([9.0, 1.0, 5.0], 100) == 9.0

    def test_sinir_disi_yuzde_kirpilir(self):
        """0–100 dışındaki yüzde istekleri sınıra kırpılmalı."""
        degerler = [1.0, 2.0, 3.0]
        assert hesapla_yuzdelik(degerler, -10) == 1.0
        assert hesapla_yuzdelik(degerler, 150) == 3.0


class TestGecikmeIstatistikleri:
    """hesapla_gecikme_istatistikleri birim testleri."""

    def test_bos_giris(self):
        """Boş girişte tüm alanlar 0 olmalı (bölme hatası yok)."""
        sonuc = hesapla_gecikme_istatistikleri([])
        assert sonuc["ortalama"] == 0.0
        assert sonuc["p99"] == 0.0
        assert sonuc["olcum_sayisi"] == 0

    def test_bilinen_degerler(self):
        """Sabit örnekte ortalama/medyan/min/max doğru hesaplanmalı."""
        sonuc = hesapla_gecikme_istatistikleri([0.1, 0.2, 0.3])
        assert sonuc["ortalama"] == pytest.approx(0.2)
        assert sonuc["medyan"] == pytest.approx(0.2)
        assert sonuc["min"] == pytest.approx(0.1)
        assert sonuc["max"] == pytest.approx(0.3)
        assert sonuc["olcum_sayisi"] == 3

    def test_kuyruk_yuzdelikleri_sirali(self):
        """p95 ≤ p99 ≤ max sıralaması her zaman korunmalı."""
        degerler = [0.01] * 90 + [0.5] * 9 + [2.0]
        sonuc = hesapla_gecikme_istatistikleri(degerler)
        assert sonuc["medyan"] <= sonuc["p95"] <= sonuc["p99"] <= sonuc["max"]


class TestThroughput:
    """hesapla_throughput birim testleri."""

    def test_temel_hesap(self):
        """10 evrak / 2 saniye → 5 evrak/sn."""
        assert hesapla_throughput(10, 2.0) == pytest.approx(5.0)

    def test_sifir_sure(self):
        """Sıfır sürede sıfıra bölme yerine 0.0 dönmeli."""
        assert hesapla_throughput(10, 0.0) == 0.0

    def test_sifir_evrak(self):
        """Hiç evrak işlenmemişse throughput 0.0 olmalı."""
        assert hesapla_throughput(0, 5.0) == 0.0

    def test_negatif_girisler(self):
        """Negatif girişler (bozuk ölçüm) 0.0 döndürmeli."""
        assert hesapla_throughput(-1, 5.0) == 0.0
        assert hesapla_throughput(10, -5.0) == 0.0


class TestAdimDagilimi:
    """hesapla_adim_dagilimi birim testleri."""

    def _ornek_kayitlar(self):
        """İki çalıştırmalık örnek adım kayıtları."""
        return [
            [
                {"agent": "ocr", "status": "success", "sure_saniye": 0.2},
                {"agent": "classification", "status": "success", "sure_saniye": 0.1},
                {"agent": "draft_writer", "status": "atlandi", "sure_saniye": 0.0},
            ],
            [
                {"agent": "ocr", "status": "success", "sure_saniye": 0.4},
                {"agent": "classification", "status": "success", "sure_saniye": 0.1},
                {"agent": "draft_writer", "status": "atlandi", "sure_saniye": 0.0},
            ],
        ]

    def test_ortalama_yalniz_basarili_adimlarla(self):
        """Ortalama yalnızca success adımlarından hesaplanmalı."""
        dagilim = hesapla_adim_dagilimi(self._ornek_kayitlar())
        ocr = next(a for a in dagilim if a["agent"] == "ocr")
        assert ocr["calisma_sayisi"] == 2
        assert ocr["ortalama_saniye"] == pytest.approx(0.3)

    def test_atlanan_adim_ortalamayi_dusurmez(self):
        """Atlanan adım (sure 0.0) çalışma sayısına ve ortalamaya girmemeli."""
        dagilim = hesapla_adim_dagilimi(self._ornek_kayitlar())
        draft = next(a for a in dagilim if a["agent"] == "draft_writer")
        assert draft["calisma_sayisi"] == 0
        assert draft["ortalama_saniye"] == 0.0
        assert draft["pay_yuzde"] == 0.0

    def test_adim_sirasi_korunur(self):
        """Adımlar pipeline'daki ilk görülme sırasıyla listelenmeli."""
        dagilim = hesapla_adim_dagilimi(self._ornek_kayitlar())
        assert [a["agent"] for a in dagilim] == ["ocr", "classification", "draft_writer"]

    def test_pay_toplami_yuz(self):
        """Başarılı adımların payları toplamı %100 olmalı."""
        dagilim = hesapla_adim_dagilimi(self._ornek_kayitlar())
        assert sum(a["pay_yuzde"] for a in dagilim) == pytest.approx(100.0)

    def test_bos_giris(self):
        """Hiç kayıt yoksa boş liste dönmeli."""
        assert hesapla_adim_dagilimi([]) == []


class TestDogrusallik:
    """hesapla_dogrusallik birim testleri."""

    def test_dogrusal_olcekleme(self):
        """Evrak başına süre sabitse oran her ölçekte 1.0 olmalı."""
        sonuc = hesapla_dogrusallik([
            {"olcek": 1, "evrak_sayisi": 10, "toplam_sure_saniye": 1.0},
            {"olcek": 5, "evrak_sayisi": 50, "toplam_sure_saniye": 5.0},
        ])
        assert sonuc[0]["evrak_basina_saniye"] == pytest.approx(0.1)
        assert sonuc[0]["dogrusallik_orani"] == pytest.approx(1.0)
        assert sonuc[1]["dogrusallik_orani"] == pytest.approx(1.0)

    def test_dogrusal_olmayan_olcekleme(self):
        """Evrak başına süre iki katına çıkarsa oran 2.0 olmalı."""
        sonuc = hesapla_dogrusallik([
            {"olcek": 1, "evrak_sayisi": 10, "toplam_sure_saniye": 1.0},
            {"olcek": 10, "evrak_sayisi": 100, "toplam_sure_saniye": 20.0},
        ])
        assert sonuc[1]["evrak_basina_saniye"] == pytest.approx(0.2)
        assert sonuc[1]["dogrusallik_orani"] == pytest.approx(2.0)

    def test_sifir_taban(self):
        """Taban süresi 0 ise oran 0.0 dönmeli (sıfıra bölme yok)."""
        sonuc = hesapla_dogrusallik([
            {"olcek": 1, "evrak_sayisi": 10, "toplam_sure_saniye": 0.0},
            {"olcek": 5, "evrak_sayisi": 50, "toplam_sure_saniye": 5.0},
        ])
        assert sonuc[0]["dogrusallik_orani"] == 0.0
        assert sonuc[1]["dogrusallik_orani"] == 0.0

    def test_girdi_degistirilmez(self):
        """Fonksiyon girdi sözlüklerini yerinde değiştirmemeli (kopya döner)."""
        girdi = [{"olcek": 1, "evrak_sayisi": 10, "toplam_sure_saniye": 1.0}]
        hesapla_dogrusallik(girdi)
        assert "dogrusallik_orani" not in girdi[0]


class TestGoreliYol:
    """goreli_yol birim testleri (rapora mutlak yol sızmaması)."""

    def test_proje_ici_yol(self):
        """Proje kökü altındaki yol köke göre göreli yazılmalı."""
        kok = Path(__file__).resolve().parent.parent
        assert goreli_yol(kok / "data" / "raw") == "data/raw"

    def test_proje_disi_yol(self):
        """Kök dışındaki yol için yalnızca dosya adı raporlanmalı."""
        sonuc = goreli_yol("/tmp/gizli_kullanici/rapor.json")
        assert sonuc == "rapor.json"
        assert "gizli_kullanici" not in sonuc
