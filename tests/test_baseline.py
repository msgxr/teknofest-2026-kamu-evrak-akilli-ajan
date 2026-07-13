# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Saf baseline sınıflandırıcı (src/utils/baseline.py) testleri."""

from src.utils.baseline import baseline_siniflandir


class TestBaseline:
    def test_dilekce(self):
        tur, n = baseline_siniflandir("Sayın Valilik, işbu dilekçe ile arz ederim.")
        assert tur == "dilekce"
        assert n >= 1

    def test_tutanak(self):
        tur, _ = baseline_siniflandir(
            "İşbu tutanak komisyon tarafından imza altına alınmıştır."
        )
        assert tur == "tutanak"

    def test_eslesme_yoksa_diger(self):
        tur, n = baseline_siniflandir("xyz abc qwe rastgele")
        assert tur == "diger"
        assert n == 0

    def test_bos_metin(self):
        assert baseline_siniflandir("")[0] == "diger"
