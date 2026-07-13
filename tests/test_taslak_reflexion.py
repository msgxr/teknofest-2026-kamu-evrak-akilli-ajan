# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Reflexion/Self-Refine yardımcılarının (src/utils/taslak_reflexion.py) testleri."""

from src.utils.taslak_reflexion import yapisal_geri_bildirim


class TestYapisalGeriBildirim:
    def test_basarisiz_kural_notu_ureter(self):
        val = {"kontroller": [
            {"kural_id": "kapanis", "kural": "Kapanış ifadesi", "durum": False,
             "detay": "Kapanış bulunamadı"},
            {"kural_id": "konu", "kural": "Konu satırı", "durum": True, "detay": ""},
        ]}
        not_ = yapisal_geri_bildirim(val)
        assert "Kapanış" in not_
        assert "Konu satırı" not in not_  # geçen kural nota alınmaz

    def test_hepsi_gecerse_bos(self):
        val = {"kontroller": [
            {"kural_id": "konu", "kural": "Konu", "durum": True, "detay": ""},
        ]}
        assert yapisal_geri_bildirim(val) == ""

    def test_bos_kontrol(self):
        assert yapisal_geri_bildirim({"kontroller": []}) == ""
        assert yapisal_geri_bildirim({}) == ""

    def test_azami_sinir(self):
        val = {"kontroller": [
            {"kural_id": f"k{i}", "kural": f"Kural {i}", "durum": False, "detay": ""}
            for i in range(10)
        ]}
        not_ = yapisal_geri_bildirim(val, azami=3)
        assert not_.count("\n- ") <= 3
