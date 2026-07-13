"""Bulanık dizgi eşleme (Damerau-Levenshtein) birim testleri."""
import pytest

from src.utils.bulanik import benzerlik, damerau_levenshtein, en_yakin


@pytest.mark.parametrize("a,b,beklenen", [
    ("", "", 0),
    ("abc", "abc", 0),
    ("abc", "", 3),
    ("", "abc", 3),
    ("kitten", "sitting", 3),        # klasik Levenshtein örneği
    ("ab", "ba", 1),                 # transpozisyon = tek işlem (Damerau)
    ("mevzuat", "mevzat", 1),        # harf düşmesi
    ("siniflandir", "sniflandir", 1),  # harf düşmesi
    ("yonlendir", "yonledir", 1),    # harf düşmesi
])
def test_damerau_levenshtein(a, b, beklenen):
    assert damerau_levenshtein(a, b) == beklenen


def test_transpozisyon_leventshtein_den_dusuk():
    # "ab"->"ba": Damerau 1 (transpozisyon), düz Levenshtein 2 olurdu.
    assert damerau_levenshtein("ab", "ba") == 1


def test_tavan_erken_cikis():
    # Çok farklı dizgilerde tavan aşılırsa tavan+1 döner (değer >= gerçek değil,
    # sadece "tavandan büyük" bilgisi yeterli).
    d = damerau_levenshtein("abcdef", "zzzzzz", tavan=2)
    assert d == 3  # tavan + 1


@pytest.mark.parametrize("a,b", [
    ("mevzuat", "mevzat"),
    ("yonlendir", "yonledir"),
])
def test_benzerlik_yuksek(a, b):
    assert benzerlik(a, b) >= 0.8


def test_benzerlik_birebir():
    assert benzerlik("ozet", "ozet") == 1.0


def test_benzerlik_alakasiz_dusuk():
    assert benzerlik("ozet", "kuantum") < 0.5


def test_en_yakin_secer():
    kelime, skor = en_yakin("yonledir", ["ozet", "yonlendir", "mevzuat"], esik=0.8)
    assert kelime == "yonlendir"
    assert skor >= 0.8


def test_en_yakin_esik_alti_none():
    kelime, skor = en_yakin("kuantum", ["ozet", "yonlendir"], esik=0.8)
    assert kelime is None
    assert skor == 0.0
