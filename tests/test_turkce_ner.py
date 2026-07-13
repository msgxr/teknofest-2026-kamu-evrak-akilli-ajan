# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Türkçe NER modülünün (src/utils/turkce_ner.py) birim testleri."""

from src.utils.turkce_ner import ILLER, varlik_f1, yer_cikar


class TestYerCikar:
    def test_il_gazetteer(self):
        y = yer_cikar("Ankara'dan İstanbul'a evrak gönderildi.")
        assert "Ankara" in y
        assert "İstanbul" in y

    def test_desen_valilik_belediye(self):
        y = yer_cikar("Bursa Valiliği ve Kadıköy İlçesi yazışması.")
        assert "Bursa Valiliği" in y
        assert "Kadıköy İlçesi" in y

    def test_benzersiz_sira_korunur(self):
        y = yer_cikar("Ankara ve Ankara ve İzmir")
        assert y == ["Ankara", "İzmir"]

    def test_yer_yoksa_bos(self):
        assert yer_cikar("herhangi bir sıradan metin buraya") == []

    def test_bos_metin(self):
        assert yer_cikar("") == []

    def test_iller_81(self):
        assert len(ILLER) == 81


class TestVarlikF1:
    def test_tam_eslesme(self):
        assert varlik_f1(["Ankara", "İzmir"], ["Ankara", "İzmir"])["f1"] == 1.0

    def test_kismi(self):
        r = varlik_f1(["Ankara", "İzmir"], ["Ankara", "Bursa"])
        assert 0.0 < r["f1"] < 1.0
        assert r["precision"] == 0.5

    def test_bos(self):
        assert varlik_f1([], [])["f1"] == 0.0
