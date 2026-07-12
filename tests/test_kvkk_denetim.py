"""KVKK maskeleme kaçak denetimi (src/utils/kvkk_denetim.py) testleri."""

from src.utils.kvkk_denetim import kacak_olc


class TestKacakOlc:
    def test_maskeli_metin_sizintisiz(self):
        # Maskelenmiş değerler "*" içerir → desenle eşleşmez → sızıntı yok
        k = kacak_olc("Tel 05** *** ****, e-posta a***@x.com, IBAN TR********************1326")
        assert k["toplam"] == 0

    def test_maskesiz_eposta_yakalanir(self):
        k = kacak_olc("İletişim: ali@ornek.com")
        assert k["eposta"] == 1
        assert k["toplam"] >= 1

    def test_maskesiz_telefon_yakalanir(self):
        assert kacak_olc("Tel: 0555 123 4567")["telefon"] == 1

    def test_gecerli_tckn_kacak(self):
        # Checksum GEÇERLİ kurgu TCKN → maskesiz kalırsa kaçaktır
        assert kacak_olc("Kimlik: 10000000146")["tckn"] == 1

    def test_gecersiz_tckn_kacak_degil(self):
        # Checksum geçmeyen 11 hane gerçek PII değildir → kaçak sayılmaz
        assert kacak_olc("Numara: 12345678901")["tckn"] == 0

    def test_bos_metin(self):
        assert kacak_olc("")["toplam"] == 0
