# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Split conformal prediction modülünün (src/utils/konformal.py) testleri."""

from src.utils.konformal import (
    konformal_degerlendirme,
    konformal_esik,
    tahmin_kumesi,
    uygunsuzluk_skorlari,
)


class TestUygunsuzluk:
    def test_dogru_sinif_skoru(self):
        s = uygunsuzluk_skorlari([{"a": 0.9, "b": 0.1}], ["a"])
        assert abs(s[0] - 0.1) < 1e-9

    def test_yanlis_sinif_yuksek_skor(self):
        s = uygunsuzluk_skorlari([{"a": 0.9, "b": 0.1}], ["b"])
        assert abs(s[0] - 0.9) < 1e-9


class TestEsik:
    def test_bos_liste(self):
        assert konformal_esik([]) == 1.0

    def test_kucuk_n_tam_kapsama(self):
        # n küçükken düzeltme n'i aşar → muhafazakâr tam kapsama (eşik 1.0)
        assert konformal_esik([0.1, 0.2], alfa=0.1) == 1.0


class TestTahminKumesi:
    def test_yuksek_olasilik_tekil(self):
        assert tahmin_kumesi({"a": 0.95, "b": 0.03, "c": 0.02}, esik=0.1) == ["a"]

    def test_bos_kume_max_alir(self):
        # Hiçbir sınıf eşiği geçmezse boş küme yerine en olası sınıf alınır
        k = tahmin_kumesi({"a": 0.5, "b": 0.5}, esik=0.0)
        assert len(k) == 1

    def test_genis_esik_coklu_kume(self):
        k = tahmin_kumesi({"a": 0.5, "b": 0.45, "c": 0.05}, esik=0.6)
        assert set(k) >= {"a", "b"}


class TestDegerlendirme:
    def test_kapsama_hedefe_yakin(self):
        olas = [{"a": 0.9, "b": 0.1}] * 20
        dogru = ["a"] * 20
        r = konformal_degerlendirme(olas, dogru, alfa=0.1)
        assert r["hedef_kapsama"] == 0.9
        assert r["ampirik_kapsama"] >= 0.9  # kapsama garantisi
        assert 1.0 <= r["ortalama_kume_boyutu"] <= 2.0

    def test_bos(self):
        assert konformal_degerlendirme([], [])["n"] == 0
