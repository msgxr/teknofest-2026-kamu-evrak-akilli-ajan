# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Öz-tutarlılık oylaması (src/utils/oz_tutarlilik.py) testleri."""

from src.utils.oz_tutarlilik import cogunluk_oyu


class TestCogunlukOyu:
    def test_hemfikir_tam_uzlasi(self):
        assert cogunluk_oyu(["dilekce", "dilekce", "dilekce"]) == ("dilekce", 1.0)

    def test_cogunluk_ve_uzlasi(self):
        karar, uzlasi = cogunluk_oyu(["dilekce", "dilekce", "rapor"])
        assert karar == "dilekce"
        assert abs(uzlasi - 0.6667) < 1e-3

    def test_bos(self):
        assert cogunluk_oyu([]) == (None, 0.0)

    def test_none_elenir(self):
        assert cogunluk_oyu([None, "rapor", None]) == ("rapor", 1.0)
