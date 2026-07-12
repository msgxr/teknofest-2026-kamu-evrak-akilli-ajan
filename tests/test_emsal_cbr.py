"""Emsal-tabanlı akıl yürütme (src/utils/emsal_cbr.py) testleri."""

from src.utils.emsal_cbr import emsal_onerisi


class TestEmsalOnerisi:
    def test_bos_emsal_none(self):
        assert emsal_onerisi([]) is None

    def test_gecersiz_kayit_elenir(self):
        assert emsal_onerisi([{"foo": "bar"}]) is None

    def test_cogunluk_uyumlu(self):
        emsaller = [
            {"tur": "dilekce", "birim": "yazi_isleri"},
            {"tur": "dilekce", "birim": "hukuk"},
            {"tur": "rapor", "birim": "yazi_isleri"},
        ]
        r = emsal_onerisi(emsaller, mevcut_tur="dilekce", mevcut_birim="yazi_isleri")
        assert r["emsal_sayisi"] == 3
        assert r["cogunluk_tur"] == "dilekce"
        assert r["cogunluk_birim"] == "yazi_isleri"
        assert r["celiskiler"] == []  # karar emsalle uyumlu

    def test_celiski_uyarisi(self):
        emsaller = [
            {"tur": "rapor", "birim": "hukuk"},
            {"tur": "rapor", "birim": "hukuk"},
        ]
        r = emsal_onerisi(emsaller, mevcut_tur="dilekce", mevcut_birim="yazi_isleri")
        assert len(r["celiskiler"]) == 2  # hem tür hem birim çelişiyor

    def test_advisory_karari_ezmez(self):
        # Öneri yalnızca bilgi döndürür; bir karar alanı içermez
        r = emsal_onerisi([{"tur": "rapor", "birim": "hukuk"}])
        assert "karar" not in r
        assert "cogunluk_tur" in r
