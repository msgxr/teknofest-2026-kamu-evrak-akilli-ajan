# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""İstatistiksel anlamlılık modülünün (src/utils/istatistik.py) testleri."""

from src.utils.istatistik import (
    bootstrap_araligi,
    mcnemar,
    oran_ozeti,
    wilson_araligi,
)


class TestWilson:
    def test_tam_basari_alt_sinir_bir_degil(self):
        alt, ust = wilson_araligi(16, 16)
        assert ust == 1.0
        assert alt < 1.0  # 16/16 olsa bile Wilson alt sınırı <1 (dürüstlük)

    def test_yari_basari(self):
        alt, ust = wilson_araligi(8, 16)
        assert alt < 0.5 < ust

    def test_sifir_toplam(self):
        assert wilson_araligi(0, 0) == [0.0, 0.0]


class TestBootstrap:
    def test_deterministik(self):
        m = [True] * 12 + [False] * 4
        assert bootstrap_araligi(m) == bootstrap_araligi(m)

    def test_hepsi_dogru(self):
        assert bootstrap_araligi([True] * 10) == [1.0, 1.0]

    def test_aralik_noktayi_icerir(self):
        alt, ust = bootstrap_araligi([True] * 12 + [False] * 4)  # nokta 0.75
        assert alt <= 0.75 <= ust


class TestMcNemar:
    def test_fark_yoksa_anlamsiz(self):
        r = mcnemar([True, True, False], [True, True, False])
        assert r["anlamli_0_05"] is False

    def test_buyuk_fark_anlamli(self):
        r = mcnemar([True] * 20, [False] * 20)
        assert r["b"] == 20 and r["c"] == 0
        assert r["anlamli_0_05"] is True


class TestOranOzeti:
    def test_yapisi(self):
        r = oran_ozeti([True] * 12 + [False] * 4)
        assert r["nokta"] == 0.75
        assert r["basari"] == 12 and r["toplam"] == 16
        assert len(r["wilson_95"]) == 2
        assert len(r["bootstrap_95"]) == 2
