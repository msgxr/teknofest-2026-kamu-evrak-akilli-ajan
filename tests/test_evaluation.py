"""
Değerlendirme Aracı metrik fonksiyonlarının birim testleri.

scripts/evaluate.py içindeki saf metrik fonksiyonlarını (accuracy,
precision/recall/F1, set karşılaştırması, medyan, adım ortalamaları)
pipeline ÇALIŞTIRMADAN, küçük sabit örneklerle test eder.

Şartname Referansı:
    "Puanlamada sınıflandırma doğruluğu, yönlendirme başarımı ve
     eksik bilgi tespiti ölçülecektir." — bu metriklerin doğru
    hesaplandığının kanıtı.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.evaluate import (
    hesapla_accuracy,
    hesapla_adim_ortalamalari,
    hesapla_medyan,
    hesapla_set_metrikleri,
    hesapla_sinif_metrikleri,
    hesapla_yanlis_listesi,
)


class TestAccuracy:
    """hesapla_accuracy birim testleri."""

    def test_tam_dogru(self):
        """Tüm tahminler doğruysa accuracy 1.0 olmalı."""
        assert hesapla_accuracy(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_tam_yanlis(self):
        """Tüm tahminler yanlışsa accuracy 0.0 olmalı."""
        assert hesapla_accuracy(["a", "b"], ["b", "a"]) == 0.0

    def test_kismi_dogru(self):
        """4 örnekten 3'ü doğruysa accuracy 0.75 olmalı."""
        gercek = ["dilekce", "tutanak", "rapor", "dilekce"]
        tahmin = ["dilekce", "tutanak", "rapor", "genelge"]
        assert hesapla_accuracy(gercek, tahmin) == 0.75

    def test_bos_giris(self):
        """Boş girişte 0.0 dönmeli (sıfıra bölme olmamalı)."""
        assert hesapla_accuracy([], []) == 0.0

    def test_uzunluk_uyusmazligi(self):
        """Farklı uzunluktaki listelerde 0.0 dönmeli."""
        assert hesapla_accuracy(["a", "b"], ["a"]) == 0.0


class TestSinifMetrikleri:
    """hesapla_sinif_metrikleri (precision/recall/F1, macro-F1) testleri."""

    def test_mukemmel_siniflandirma(self):
        """Kusursuz tahminde tüm metrikler 1.0 olmalı."""
        gercek = ["dilekce", "tutanak", "dilekce"]
        sonuc = hesapla_sinif_metrikleri(gercek, list(gercek))
        assert sonuc["macro_f1"] == 1.0
        assert sonuc["sinif_bazinda"]["dilekce"]["precision"] == 1.0
        assert sonuc["sinif_bazinda"]["dilekce"]["recall"] == 1.0
        assert sonuc["sinif_bazinda"]["dilekce"]["f1"] == 1.0
        assert sonuc["sinif_bazinda"]["dilekce"]["destek"] == 2
        assert sonuc["sinif_bazinda"]["tutanak"]["destek"] == 1

    def test_bilinen_degerler(self):
        """Elle hesaplanmış TP/FP/FN değerleriyle doğrulama.

        gercek: [a, a, b, b], tahmin: [a, b, b, b]
        a: TP=1, FP=0, FN=1 → P=1.0,  R=0.5,  F1=2/3
        b: TP=2, FP=1, FN=0 → P=2/3,  R=1.0,  F1=0.8
        macro-F1 = (2/3 + 0.8) / 2 = 0.7333
        """
        sonuc = hesapla_sinif_metrikleri(["a", "a", "b", "b"], ["a", "b", "b", "b"])
        a = sonuc["sinif_bazinda"]["a"]
        b = sonuc["sinif_bazinda"]["b"]
        assert a["precision"] == 1.0
        assert a["recall"] == 0.5
        assert a["f1"] == pytest.approx(2 / 3, abs=1e-3)
        assert b["precision"] == pytest.approx(2 / 3, abs=1e-3)
        assert b["recall"] == 1.0
        assert b["f1"] == pytest.approx(0.8, abs=1e-3)
        assert sonuc["macro_f1"] == pytest.approx(0.7333, abs=1e-3)

    def test_hic_tahmin_edilmeyen_sinif(self):
        """Hiç tahmin edilmeyen sınıfta precision/recall 0 olmalı (bölme hatasız)."""
        sonuc = hesapla_sinif_metrikleri(["a", "b"], ["a", "a"])
        assert sonuc["sinif_bazinda"]["b"]["precision"] == 0.0
        assert sonuc["sinif_bazinda"]["b"]["recall"] == 0.0
        assert sonuc["sinif_bazinda"]["b"]["f1"] == 0.0

    def test_sadece_tahminde_gorulen_sinif(self):
        """Etikette olmayan ama tahminde görülen sınıf da tabloda yer almalı."""
        sonuc = hesapla_sinif_metrikleri(["a", "a"], ["a", "c"])
        assert "c" in sonuc["sinif_bazinda"]
        assert sonuc["sinif_bazinda"]["c"]["precision"] == 0.0
        assert sonuc["sinif_bazinda"]["c"]["destek"] == 0

    def test_bos_giris(self):
        """Boş girişte macro metrikler 0.0 olmalı."""
        sonuc = hesapla_sinif_metrikleri([], [])
        assert sonuc["macro_f1"] == 0.0
        assert sonuc["sinif_bazinda"] == {}


class TestSetMetrikleri:
    """hesapla_set_metrikleri (eksik bilgi tespiti, micro P/R/F1) testleri."""

    def test_tam_eslesme(self):
        """Kümeler birebir eşleşiyorsa micro F1 1.0 olmalı."""
        ciftler = [({"imza", "tarih"}, {"imza", "tarih"})]
        sonuc = hesapla_set_metrikleri(ciftler)
        assert sonuc["micro_f1"] == 1.0
        assert sonuc["tp"] == 2
        assert sonuc["fp"] == 0
        assert sonuc["fn"] == 0

    def test_bilinen_degerler(self):
        """Elle hesaplanmış micro değerlerle doğrulama.

        Evrak 1: gercek={imza, tarih},  tahmin={imza}        → TP=1, FN=1
        Evrak 2: gercek={sayi},         tahmin={sayi, konu}  → TP=1, FP=1
        Toplam: TP=2, FP=1, FN=1 → P=2/3, R=2/3, F1=2/3
        """
        ciftler = [
            ({"imza", "tarih"}, {"imza"}),
            ({"sayi"}, {"sayi", "konu"}),
        ]
        sonuc = hesapla_set_metrikleri(ciftler)
        assert sonuc["tp"] == 2
        assert sonuc["fp"] == 1
        assert sonuc["fn"] == 1
        assert sonuc["micro_precision"] == pytest.approx(2 / 3, abs=1e-3)
        assert sonuc["micro_recall"] == pytest.approx(2 / 3, abs=1e-3)
        assert sonuc["micro_f1"] == pytest.approx(2 / 3, abs=1e-3)

    def test_bos_kumeler(self):
        """İki taraf da boşsa (eksik yok, tespit yok) sıfıra bölme olmamalı."""
        sonuc = hesapla_set_metrikleri([(set(), set())])
        assert sonuc["micro_f1"] == 0.0
        assert sonuc["tp"] == 0

    def test_liste_girisi_kabul_edilmeli(self):
        """Küme yerine liste verilse de çalışmalı (etiket JSON'dan liste gelir)."""
        sonuc = hesapla_set_metrikleri([(["imza", "tarih"], ["imza"])])
        assert sonuc["tp"] == 1
        assert sonuc["fn"] == 1

    def test_bos_ciftler_listesi(self):
        """Hiç evrak yoksa tüm metrikler 0.0 olmalı."""
        sonuc = hesapla_set_metrikleri([])
        assert sonuc["micro_precision"] == 0.0
        assert sonuc["micro_recall"] == 0.0
        assert sonuc["micro_f1"] == 0.0


class TestMedyan:
    """hesapla_medyan testleri."""

    def test_tek_eleman(self):
        assert hesapla_medyan([2.5]) == 2.5

    def test_tek_sayida_eleman(self):
        """Sırasız girişte de ortadaki değer dönmeli."""
        assert hesapla_medyan([3.0, 1.0, 2.0]) == 2.0

    def test_cift_sayida_eleman(self):
        """Çift eleman sayısında ortadaki iki değerin ortalaması dönmeli."""
        assert hesapla_medyan([1.0, 2.0, 3.0, 4.0]) == 2.5

    def test_bos_liste(self):
        assert hesapla_medyan([]) == 0.0


class TestYanlisListesi:
    """hesapla_yanlis_listesi (confusion özeti) testleri."""

    def test_yanlislar_listelenmeli(self):
        sonuc = hesapla_yanlis_listesi(
            ["a.txt", "b.txt", "c.txt"],
            ["dilekce", "tutanak", "rapor"],
            ["dilekce", "rapor", "rapor"],
        )
        assert sonuc == [
            {"dosya": "b.txt", "beklenen": "tutanak", "tahmin": "rapor"}
        ]

    def test_hepsi_dogruysa_bos(self):
        assert hesapla_yanlis_listesi(["a.txt"], ["x"], ["x"]) == []


class TestAdimOrtalamalari:
    """hesapla_adim_ortalamalari (adım bazında süre) testleri."""

    def test_iki_evrak_ortalamasi(self):
        """Aynı agent'ın iki evraktaki sürelerinin ortalaması alınmalı."""
        tum_adimlar = [
            [{"agent": "ocr", "sure_saniye": 0.2},
             {"agent": "classification", "sure_saniye": 0.1}],
            [{"agent": "ocr", "sure_saniye": 0.4}],
        ]
        sonuc = hesapla_adim_ortalamalari(tum_adimlar)
        assert sonuc["ocr"] == pytest.approx(0.3, abs=1e-6)
        assert sonuc["classification"] == pytest.approx(0.1, abs=1e-6)

    def test_bos_giris(self):
        assert hesapla_adim_ortalamalari([]) == {}
