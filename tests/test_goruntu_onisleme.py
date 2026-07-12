"""Adaptif görüntü ön-işleme (src/utils/goruntu_onisleme.py) testleri.

cv2/PIL/numpy varsa tam hat; yoksa graceful fallback denenir.
"""

import pytest

from src.utils.goruntu_onisleme import ocr_kalite, on_isle

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")


def _sentetik_belge(yukseklik=200, genislik=400):
    """Beyaz zemin + siyah 'metin' bloklu sentetik görüntü."""
    arr = np.full((yukseklik, genislik), 255, dtype=np.uint8)
    for satir in range(40, yukseklik - 40, 30):
        arr[satir:satir + 10, 40:genislik - 40] = 0  # metin benzeri çizgiler
    return Image.fromarray(arr)


class TestOnIsle:
    def test_goruntu_islenir_ve_pil_doner(self):
        sonuc = on_isle(_sentetik_belge())
        assert sonuc is not None
        assert hasattr(sonuc, "size")  # PIL Image

    def test_kucuk_goruntu_buyutulur(self):
        # cv2 varsa 100px yükseklik >=1000'e ölçeklenir
        sonuc = on_isle(_sentetik_belge(yukseklik=100, genislik=300))
        assert sonuc.size[1] >= 100  # en azından küçülmemiş

    def test_hata_yukseltmez(self):
        # Bozuk/None girdide bile çökmez (güvenli katman)
        assert on_isle(None) is None


class TestOcrKalite:
    def test_yuksek_guven(self):
        r = ocr_kalite([95, 90, 88, 92])
        assert r["kalite"] == "yuksek"
        assert r["insan_onayi_onerilir"] is False

    def test_dusuk_guven_insan_onayi(self):
        r = ocr_kalite([30, 40, 25, 50])
        assert r["kalite"] == "dusuk"
        assert r["insan_onayi_onerilir"] is True

    def test_bos_dusuk(self):
        assert ocr_kalite([])["kalite"] == "dusuk"

    def test_negatif_conf_elenir(self):
        # -1 (Tesseract boş) değerler elenir
        r = ocr_kalite([-1, 90, -1, 88])
        assert r["ortalama_guven"] == 89.0
