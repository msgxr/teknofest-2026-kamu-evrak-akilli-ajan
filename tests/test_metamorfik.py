# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Metamorfik perturbasyon modülünün (src/utils/metamorfik.py) birim testleri.

Bozulmaların deterministik ve (makul ölçüde) etiket-koruyan olduğunu doğrular.
"""

import random

from src.utils.metamorfik import (
    PERTURBASYONLAR,
    bosluk_gurultu,
    diyakritik_katla,
    invaryans_orani,
    noktalama_gurultu,
    ocr_ikame,
    varyant_uret,
    yazim_gurultu,
)


class TestDiyakritik:
    def test_tum_diyakritikler_duzlesir(self):
        r = diyakritik_katla("çğışöüÇĞİÖŞÜ", random.Random(0))
        assert r == "cgisouCGIOSU"

    def test_diyakritiksiz_metin_degismez(self):
        assert diyakritik_katla("abc DEF 123", random.Random(0)) == "abc DEF 123"


class TestDeterminizm:
    def test_ayni_tohum_ayni_cikti(self):
        metin = "Bu bir örnek resmî yazışma metnidir ve yeterince uzundur."
        for fn in (bosluk_gurultu, yazim_gurultu, ocr_ikame, noktalama_gurultu):
            a = fn(metin, random.Random(42))
            b = fn(metin, random.Random(42))
            assert a == b, f"{fn.__name__} deterministik değil"


class TestEtiketKoruma:
    def test_yazim_ilk_son_harf_korunur(self):
        # Transpozisyon yalnızca orta harflerde; ilk/son harf değişmez
        metin = "müdürlüğüne başvurulmuştur talebiyle"
        r = yazim_gurultu(metin, random.Random(1))
        for orig, boz in zip(metin.split(" "), r.split(" ")):
            if len(orig) >= 6:
                assert orig[0] == boz[0]
                assert orig[-1] == boz[-1]
            # kelime uzunluğu korunur (transpozisyon)
            assert len(orig) == len(boz)

    def test_bosluk_gurultu_kelimeleri_korur(self):
        metin = "genel müdürlük yazı işleri"
        r = bosluk_gurultu(metin, random.Random(3))
        assert r.split() == metin.split()  # kelimeler aynı, yalnız boşluk artar

    def test_kisa_metin_cokmez(self):
        for fn in PERTURBASYONLAR.values():
            assert isinstance(fn("ab", random.Random(0)), str)
            assert isinstance(fn("", random.Random(0)), str)


class TestVaryantUret:
    def test_tum_perturbasyonlar(self):
        v = varyant_uret("Yeterince uzun bir örnek metin buraya yazıldı.", tohum=7)
        assert len(v) == len(PERTURBASYONLAR)
        adlar = [ad for ad, _ in v]
        assert set(adlar) == set(PERTURBASYONLAR)

    def test_secili_perturbasyon(self):
        v = varyant_uret("örnek metin", tohum=1, perturbasyon_adlari=["diyakritik"])
        assert len(v) == 1
        assert v[0][0] == "diyakritik"

    def test_deterministik(self):
        a = varyant_uret("Aynı tohum aynı sonucu vermeli değil mi acaba", tohum=9)
        b = varyant_uret("Aynı tohum aynı sonucu vermeli değil mi acaba", tohum=9)
        assert a == b


class TestInvaryans:
    def test_hepsi_ayni_tam_invaryans(self):
        assert invaryans_orani("dilekce", ["dilekce", "dilekce", "dilekce"]) == 1.0

    def test_yari_farkli(self):
        assert invaryans_orani("dilekce", ["dilekce", "rapor"]) == 0.5

    def test_bos_varyant(self):
        assert invaryans_orani("dilekce", []) == 1.0


class TestDayaniklilikSmoke:
    """dayaniklilik_testi scriptinin küçük uçtan uca dumanı (2 evrak)."""

    def test_kucuk_kosum(self):
        from pathlib import Path

        from scripts.dayaniklilik_testi import dayaniklilik_olc

        veri = Path(__file__).parent.parent / "data" / "raw" / "kurgu_evraklar"
        rapor = dayaniklilik_olc(veri, tohum=1, azami_dosya=2)
        assert rapor["degerlendirilen_evrak"] == 2
        assert 0.0 <= rapor["tur_invaryans"] <= 1.0
        assert 0.0 <= rapor["gurbuz_dogruluk"] <= 1.0
        assert set(rapor["bozulma_bazinda"]) == set(PERTURBASYONLAR)
