# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Özet kalitesi modülünün (src/utils/ozet_kalite.py) birim testleri."""

from src.utils.ozet_kalite import (
    kaynak_kapsama,
    ozet_kalite_raporu,
    rouge_l,
    sadakat,
    sadelestir,
    sadelestir_guvenli,
    sikistirma_orani,
)


class TestSadakat:
    def test_olgular_kaynakta_var(self):
        kaynak = "15.01.2026 tarihli 3071 sayılı başvuru işleme alındı."
        ozet = "3071 sayılı başvuru 15.01.2026 tarihinde alındı."
        assert sadakat(ozet, kaynak) == 1.0

    def test_uydurma_sayi_dusuk_sadakat(self):
        kaynak = "3071 sayılı başvuru alındı."
        ozet = "9999 sayılı başvuru alındı."  # kaynakta olmayan sayı
        assert sadakat(ozet, kaynak) < 1.0

    def test_olgusuz_ozet_tam_sadakat(self):
        assert sadakat("herhangi bir metin", "kaynak metin") == 1.0


class TestKaynakKapsama:
    def test_tum_olgular_ozette(self):
        assert kaynak_kapsama("3071 ve 2026", "3071 sayılı 2026 yılı") == 1.0

    def test_hicbiri_yok(self):
        assert kaynak_kapsama("hiç sayı yok", "3071 sayılı 2026 yılı") == 0.0

    def test_kaynakta_olgu_yoksa_none(self):
        assert kaynak_kapsama("özet", "sayısız kaynak metni") is None


class TestSikistirma:
    def test_orani(self):
        assert sikistirma_orani("a b", "a b c d") == 0.5

    def test_bos_kaynak(self):
        assert sikistirma_orani("a", "") == 0.0


class TestRougeL:
    def test_ozdes_bir(self):
        assert rouge_l("aynı metin burada", "aynı metin burada") == 1.0

    def test_ortak_yok(self):
        assert rouge_l("bir iki üç", "dört beş altı") == 0.0

    def test_bos(self):
        assert rouge_l("", "x") == 0.0


class TestSadelestir:
    def test_sayisiz_parantez_atilir(self):
        assert "(açıklama notu)" not in sadelestir("Karar verildi (açıklama notu).")

    def test_sayili_parantez_korunur(self):
        # Mevzuat/tarih içeren parantez KORUNUR (sadakat)
        r = sadelestir("Başvuru (3071 sayılı Kanun) uyarınca alındı.")
        assert "3071" in r

    def test_bastaki_doldurucu_atilir(self):
        r = sadelestir("Ayrıca, evrak arşive kaldırıldı.")
        assert not r.lower().startswith("ayrıca")

    def test_bos(self):
        assert sadelestir("") == ""


class TestSadelestirGuvenli:
    def test_olgu_korunur(self):
        cumle = "Başvuru (3071 sayılı Kanun) 15.01.2026 tarihinde alındı."
        r = sadelestir_guvenli(cumle)
        assert "3071" in r and "15.01.2026" in r

    def test_rapor_anahtarlari(self):
        r = ozet_kalite_raporu("3071 özeti", "3071 sayılı kaynak")
        assert set(r) == {"sadakat", "kaynak_kapsama", "sikistirma_orani"}
