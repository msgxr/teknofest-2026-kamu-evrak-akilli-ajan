"""Seçici sınıflandırma modülünün (src/utils/secici_tahmin.py) testleri."""

from src.utils.secici_tahmin import belirsizlik_skoru, chow_reddet, kapsam_risk


class TestBelirsizlik:
    def test_yuksek_guven_dusuk_belirsizlik(self):
        r = belirsizlik_skoru({"a": 0.95, "b": 0.03, "c": 0.02})
        assert r["msp"] == 0.95
        assert r["belirsizlik"] < 0.3

    def test_kararsiz_yuksek_belirsizlik(self):
        # İki tür arasında kararsız (marj küçük) → yüksek belirsizlik
        r = belirsizlik_skoru({"a": 0.5, "b": 0.48})
        assert r["marj"] < 0.1
        assert r["belirsizlik"] > 0.4

    def test_oov_belirsizligi_artirir(self):
        dusuk = belirsizlik_skoru({"a": 0.9, "b": 0.1}, oov_orani=0.0)["belirsizlik"]
        yuksek = belirsizlik_skoru({"a": 0.9, "b": 0.1}, oov_orani=1.0)["belirsizlik"]
        assert yuksek > dusuk

    def test_bos(self):
        assert belirsizlik_skoru({})["belirsizlik"] == 1.0


class TestChow:
    def test_esik_altinda_reddet(self):
        assert chow_reddet(0.4, 0.6) is True
        assert chow_reddet(0.7, 0.6) is False
        assert chow_reddet(0.6, 0.6) is False  # eşik dahil kabul


class TestKapsamRisk:
    def test_hepsi_kabul(self):
        r = kapsam_risk([0.9, 0.8], [True, True], esik=0.6)
        assert r["kapsama"] == 1.0
        assert r["risk"] == 0.0
        assert r["reddedilen"] == 0

    def test_dusuk_guven_reddedilir(self):
        # 0.4 reddedilir; kabul edilen 0.9 doğru → risk 0
        r = kapsam_risk([0.9, 0.4], [True, False], esik=0.6)
        assert r["reddedilen"] == 1
        assert r["kapsama"] == 0.5
        assert r["risk"] == 0.0

    def test_reddetme_hatayi_eler(self):
        # Yüksek güvenli yanlış yoksa, reddetme riski düşürür
        guvenler = [0.9, 0.85, 0.4, 0.3]
        dogrular = [True, True, False, False]  # düşük güvenliler yanlış
        r = kapsam_risk(guvenler, dogrular, esik=0.6)
        assert r["risk"] == 0.0  # kabul edilenlerin hepsi doğru
        assert r["reddedilen"] == 2

    def test_bos(self):
        r = kapsam_risk([], [], 0.6)
        assert r["kapsama"] == 0.0
