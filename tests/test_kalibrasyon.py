"""Güven kalibrasyonu modülünün (src/utils/kalibrasyon.py) birim testleri.

Tümü deterministik; harici bağımlılık yok.
"""

import math

import pytest

from src.utils.kalibrasyon import (
    brier_skoru,
    ece_mce,
    kalibrasyon_raporu,
    risk_kapsama,
    sicaklik_ogren,
    sicaklikla_kalibre_et,
    softmax,
)


class TestSoftmax:
    def test_olasiliklar_bire_toplanir(self):
        p = softmax({"a": 2.0, "b": 1.0, "c": 0.0})
        assert abs(sum(p.values()) - 1.0) < 1e-9

    def test_argmax_korunur(self):
        skorlar = {"a": 3.0, "b": 1.0, "c": 0.5}
        for T in (0.5, 1.0, 2.0, 5.0):
            p = softmax(skorlar, T)
            assert max(p, key=p.get) == "a"

    def test_yuksek_sicaklik_guveni_dusurur(self):
        skorlar = {"a": 3.0, "b": 1.0}
        dusuk_T = max(softmax(skorlar, 0.5).values())
        yuksek_T = max(softmax(skorlar, 5.0).values())
        assert dusuk_T > yuksek_T

    def test_bos_skor(self):
        assert softmax({}) == {}


class TestECE:
    def test_mukemmel_kalibrasyon_sifir_ece(self):
        # Hepsi güven 1.0 ve hepsi doğru → ECE = 0
        r = ece_mce([1.0] * 10, [True] * 10)
        assert r["ece"] == 0.0

    def test_asiri_guven_yuksek_ece(self):
        # Güven daima 1.0 ama yarısı yanlış → ECE ≈ 0.5
        r = ece_mce([1.0] * 10, [True] * 5 + [False] * 5)
        assert abs(r["ece"] - 0.5) < 1e-6
        assert abs(r["mce"] - 0.5) < 1e-6

    def test_bos_girdi(self):
        assert ece_mce([], [])["ece"] == 0.0

    def test_kutu_sayisi_ve_alan(self):
        r = ece_mce([0.3, 0.35, 0.9, 0.95], [False, True, True, True], kutu_sayisi=10)
        toplam = sum(k["sayi"] for k in r["kutular"])
        assert toplam == 4
        assert 0.0 <= r["ece"] <= 1.0


class TestBrier:
    def test_mukemmel(self):
        assert brier_skoru([1.0] * 5, [True] * 5) == 0.0

    def test_en_kotu(self):
        assert brier_skoru([1.0] * 5, [False] * 5) == 1.0

    def test_araligi(self):
        b = brier_skoru([0.7, 0.6, 0.9], [True, False, True])
        assert 0.0 <= b <= 1.0


class TestRiskKapsama:
    def test_hepsi_dogru_sifir_aurc(self):
        r = risk_kapsama([0.9, 0.8, 0.7], [True, True, True])
        assert r["aurc"] == 0.0

    def test_guven_hatayi_siralarsa_dusuk_aurc(self):
        # Güven yüksek olanlar doğru, düşük olanlar yanlış → iyi sıralama
        iyi = risk_kapsama([0.95, 0.9, 0.3, 0.2], [True, True, False, False])
        # Ters durum: güven yüksek olanlar yanlış → kötü sıralama
        kotu = risk_kapsama([0.95, 0.9, 0.3, 0.2], [False, False, True, True])
        assert iyi["aurc"] < kotu["aurc"]

    def test_egri_kapsama_artan(self):
        r = risk_kapsama([0.9, 0.5, 0.7], [True, False, True])
        kapsamalar = [nokta["kapsama"] for nokta in r["egri"]]
        assert kapsamalar == sorted(kapsamalar)
        assert abs(kapsamalar[-1] - 1.0) < 1e-9


class TestSicaklikOgren:
    def test_asiri_guvende_sicaklik_bir_ustunde(self):
        # Model %95 güvenle A diyor ama yalnızca %70 doğru → aşırı güven,
        # öğrenilen sıcaklık > 1 olmalı (güveni yumuşatır).
        olasiliklar = [{"a": 0.95, "b": 0.05}] * 20
        dogru = ["a"] * 14 + ["b"] * 6
        T = sicaklik_ogren(olasiliklar, dogru)
        assert T > 1.0

    def test_sicaklik_ece_dusurur(self):
        olasiliklar = [{"a": 0.95, "b": 0.05}] * 20
        dogru = ["a"] * 14 + ["b"] * 6
        dogrular = [d == "a" for d in dogru]  # tahmin daima "a"
        onceki = ece_mce([0.95] * 20, dogrular)["ece"]
        T = sicaklik_ogren(olasiliklar, dogru)
        kalibre = sicaklikla_kalibre_et(olasiliklar, T)
        sonraki = ece_mce(kalibre, dogrular)["ece"]
        assert sonraki <= onceki

    def test_bos_liste(self):
        assert sicaklik_ogren([], []) == 1.0


class TestKalibrasyonRaporu:
    def test_anahtarlar(self):
        r = kalibrasyon_raporu([0.9, 0.8], [True, False])
        for anahtar in ("n", "ece", "mce", "brier", "aurc", "reliability_kutulari"):
            assert anahtar in r
        assert r["n"] == 2

    def test_sicaklik_ogrenimi_izinliyse_alan_eklenir(self):
        olasiliklar = [{"a": 0.9, "b": 0.1}, {"a": 0.8, "b": 0.2}]
        r = kalibrasyon_raporu(
            [0.9, 0.8], [True, False],
            olasilik_listesi=olasiliklar, dogru_siniflar=["a", "a"],
            sicaklik_ogren_izinli=True,
        )
        assert "ogrenilen_sicaklik" in r
        assert "ece_kalibrasyon_sonrasi" in r

    def test_izinsizse_sicaklik_alani_yok(self):
        r = kalibrasyon_raporu([0.9], [True], sicaklik_ogren_izinli=False)
        assert "ogrenilen_sicaklik" not in r
