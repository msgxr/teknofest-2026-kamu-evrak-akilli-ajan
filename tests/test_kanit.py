"""Karar-kaynak eşlemesi (src/utils/kanit.py) testleri."""

from src.utils.kanit import vurgu_spanlari


class TestVurguSpanlari:
    def test_span_kaynaga_denk_gelir(self):
        metin = "Ankara Valiliğine. 15.01.2026 tarihli dilekçe."
        sonuc = {"bilgi_cikarim": {
            "tarihler": ["15.01.2026"], "kurum_adlari": ["Ankara Valiliği"],
        }}
        v = vurgu_spanlari(metin, sonuc)
        assert any(x["kategori"] == "tarih" for x in v)
        # Her span kaynak metinde tam olarak o değeri gösterir (grounded)
        for x in v:
            b, e = x["span"]
            assert metin[b:e] == x["deger"]

    def test_ivedilik_damgasi(self):
        v = vurgu_spanlari("ACELE\nGenel Müdürlüğe", {"bilgi_cikarim": {}})
        assert any(x["kategori"] == "damga" and x["deger"] == "ACELE" for x in v)

    def test_grounded_olmayan_atlanir(self):
        # extracted'da var ama metinde YOK → span üretilmez (halüsinasyon yok)
        v = vurgu_spanlari("kısa metin", {"bilgi_cikarim": {"tarihler": ["99.99.9999"]}})
        assert v == []

    def test_bos_metin(self):
        assert vurgu_spanlari("", {"bilgi_cikarim": {}}) == []

    def test_azami_sinir(self):
        metin = "01.01.2026 " * 100
        v = vurgu_spanlari(metin, {"bilgi_cikarim": {"tarihler": ["01.01.2026"]}}, azami=10)
        assert len(v) <= 10
