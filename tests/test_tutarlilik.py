"""Çapraz tutarlılık doğrulayıcı (src/utils/tutarlilik_denetimi.py) testleri."""

from src.utils.tutarlilik_denetimi import tutarlilik_denetle


class TestTutarlilik:
    def test_tutarli_durum(self):
        r = tutarlilik_denetle(
            ozet="3071 sayılı başvuru 15.01.2026 tarihinde alındı.",
            kaynak_metin="15.01.2026 tarihli 3071 sayılı başvuru işleme alındı.",
            taslak="... 3071 sayılı Kanun uyarınca ...",
            mevzuat_eslesmeleri=[{"baslik": "3071 sayılı Dilekçe Hakkının Kullanılması"}],
        )
        assert r["tutarli"] is True
        assert r["celiskiler"] == []
        assert r["insan_onayi_onerilir"] is False

    def test_ozet_halusinasyonu_yakalanir(self):
        r = tutarlilik_denetle(
            ozet="9999 sayılı karar alındı.",  # kaynakta olmayan sayı
            kaynak_metin="3071 sayılı başvuru.",
            taslak="", mevzuat_eslesmeleri=[],
        )
        assert r["tutarli"] is False
        assert any(c["tur"] == "ozet_sadakat" for c in r["celiskiler"])

    def test_taslak_halusinasyon_atif_yakalanir(self):
        r = tutarlilik_denetle(
            ozet="", kaynak_metin="",
            taslak="... 5237 sayılı Kanun uyarınca ...",  # öneri listesinde yok
            mevzuat_eslesmeleri=[{"baslik": "3071 sayılı Dilekçe Kanunu"}],
        )
        assert any(c["tur"] == "taslak_atif" for c in r["celiskiler"])

    def test_oneri_listesi_numarasizsa_atif_denetlenmez(self):
        # Yanlış alarm önleme: öneri listesi numara içermiyorsa taslak atfı
        # denetlenmez (numara çıkarılamadığında hepsini şüpheli sayma)
        r = tutarlilik_denetle(
            ozet="", kaynak_metin="",
            taslak="5237 sayılı Kanun",
            mevzuat_eslesmeleri=[{"baslik": "Resmî Yazışma Yönetmeliği"}],
        )
        assert all(c["tur"] != "taslak_atif" for c in r["celiskiler"])
