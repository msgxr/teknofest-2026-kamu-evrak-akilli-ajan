"""Tekrarlanabilirlik mührü modülünün (src/utils/kosum_muhru.py) testleri."""

import json
from pathlib import Path

from src.utils.kosum_muhru import kosum_muhru, set_icerik_hash

PROJE = Path(__file__).parent.parent


class TestKosumMuhru:
    def test_temel_alanlar(self):
        m = kosum_muhru(PROJE)
        for anahtar in ("git_commit", "python", "platform"):
            assert anahtar in m
        assert "." in m["python"]  # sürüm biçimi

    def test_set_hash_deterministik(self):
        veri = PROJE / "data" / "raw" / "kurgu_evraklar"
        assert set_icerik_hash(veri) == set_icerik_hash(veri)

    def test_farkli_setler_farkli_hash(self):
        h1 = set_icerik_hash(PROJE / "data" / "raw" / "kurgu_evraklar")
        h2 = set_icerik_hash(PROJE / "data" / "raw" / "kurgu_evraklar_heldout")
        assert h1 != h2

    def test_veri_dizini_verilince_set_hash(self):
        m = kosum_muhru(PROJE, PROJE / "data" / "raw" / "kurgu_evraklar")
        assert len(m["set_icerik_hash"]) == 16

    def test_mutlak_yol_sizmaz(self):
        m = kosum_muhru(PROJE, PROJE / "data" / "raw" / "kurgu_evraklar")
        assert "/Users/" not in json.dumps(m)  # mutlak yol/kullanıcı adı sızmaz
