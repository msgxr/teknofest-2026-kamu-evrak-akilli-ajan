"""
Sayı üretici (m.11) ve üstveri ↔ belge tutarlılık doğrulayıcısı (m.28/3)
birim testleri.

Yönetmelik ilkesinin ("belge görüntüsü üzerindeki bilgiler ile üstverideki
bilgiler arasında fark olamaz") birim teste çevrilmesi — P0-3.

Şartname Referansı (Görev 2): EBYS entegrasyon vizyonu / resmî yazışma
kurallarına uygunluk.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.eyazisma import uret_ustveri, ustveri_belge_tutarliligi
from src.utils.sayi_uretici import (
    KURGU_SDP_KODLARI,
    kurgu_detsis_no,
    sayi_dogrula,
    sayi_uret,
)

ORNEK_BELGE = """T.C.
AKÇOVA VALİLİĞİ
Yazı İşleri Müdürlüğü

Sayı   : E-12345678-622.01-42                       11.07.2026
Konu   : Park aydınlatması hakkında

KURGU BAKANLIĞINA

İlgi   : 01.07.2026 tarihli yazı.

Metin gövdesi.

Bilgilerinize arz ederim.
"""


class TestSayiUretici:
    """m.11 biçimli kurgu sayı üretimi testleri."""

    def test_uretilen_sayi_bicime_uyar(self):
        """Üretilen sayı m.11 desenini (E-DETSİS-SDP-kayıt) geçmeli."""
        sayi = sayi_uret("Kurgu Belediyesi", "dilekce", sira_no=42)
        assert sayi_dogrula(sayi), sayi
        assert sayi.startswith("E-")
        assert sayi.endswith("-42")

    def test_deterministik_detsis(self):
        """Aynı kurgu kurum adı her zaman aynı 8 haneli kodu üretmeli."""
        a = kurgu_detsis_no("Kurgu Belediyesi")
        b = kurgu_detsis_no("Kurgu Belediyesi")
        c = kurgu_detsis_no("Başka Kurum")
        assert a == b
        assert a != c
        assert len(a) == 8 and a[0] != "0"

    def test_tur_sdp_eslemesi(self):
        """Evrak türü kurgu dosya planı koduna eşlenmeli."""
        sayi = sayi_uret("Kurgu Kurum", "dilekce")
        assert KURGU_SDP_KODLARI["dilekce"] in sayi

    def test_gecersiz_ortam_e_olur(self):
        """Geçersiz ortam ibaresi 'E' varsayılanına düşmeli (m.11/1: E/Z/O)."""
        assert sayi_uret("Kurum", ortam="X").startswith("E-")
        assert sayi_uret("Kurum", ortam="Z").startswith("Z-")

    def test_dogrulayici_ret_ornekleri(self):
        """Biçimsiz sayılar doğrulamadan geçmemeli."""
        assert sayi_dogrula("E-67915368-903.07.02-4752") is True
        assert sayi_dogrula("2026/418") is False
        assert sayi_dogrula("E-123-903-1") is False  # DETSİS 8 hane değil
        assert sayi_dogrula("") is False


class TestUstveriBelgeAlanlari:
    """uret_ustveri'nin belge görüntüsünden birebir okuma testleri."""

    def test_belge_alanlari_birebir_okunur(self):
        """Sayı/Konu/tarih üstveriye belge görüntüsünden aynen taşınmalı."""
        ustveri = uret_ustveri({}, ORNEK_BELGE)
        assert ustveri["belge"]["sayi"] == "E-12345678-622.01-42"
        assert ustveri["belge"]["konu"] == "Park aydınlatması hakkında"
        assert ustveri["belge"]["belge_tarihi"] == "11.07.2026"

    def test_gizlilik_damgasi_guvenlik_koduna(self):
        """Belgede damga varsa güvenlik kodu damganın kendisi olmalı."""
        ustveri = uret_ustveri({}, "HİZMETE ÖZEL\n" + ORNEK_BELGE)
        assert ustveri["belge"]["guvenlik_kodu"] == "HİZMETE ÖZEL"

    def test_damgasiz_belgede_tsd(self):
        assert uret_ustveri({}, ORNEK_BELGE)["belge"]["guvenlik_kodu"] == "TSD"

    def test_geriye_donuk_uyum(self):
        """belge_metni verilmeden eski davranış (boş belge alanları) korunmalı."""
        ustveri = uret_ustveri({})
        assert ustveri["belge"]["sayi"] == ""
        assert ustveri["belge"]["guvenlik_kodu"] == "TSD"
        assert "sayi_onerisi" in ustveri["belge"]

    def test_sayi_onerisi_bicimli(self):
        """Öneri alanı m.11 biçimli olmalı (belgede yer almaz, öneridir)."""
        ustveri = uret_ustveri(
            {"yonlendirme": {"birim": "Yazı İşleri", "birim_kodu": "yazi_isleri"}}
        )
        assert sayi_dogrula(ustveri["belge"]["sayi_onerisi"])


class TestUstveriBelgeTutarliligi:
    """m.28/3 birebir eşitlik denetimi testleri."""

    def test_tutarli_ustveri(self):
        """Belgeden üretilen üstveri, aynı belgeyle birebir tutarlı olmalı."""
        ustveri = uret_ustveri({}, ORNEK_BELGE)
        sonuc = ustveri_belge_tutarliligi(ustveri, ORNEK_BELGE)
        assert sonuc["tutarli"] is True
        assert sonuc["dayanak"] == "Yön. (2646) m.28/3"

    def test_sayi_farki_yakalanir(self):
        """Üstverideki sayı belgeden farklıysa denetim başarısız olmalı."""
        ustveri = uret_ustveri({}, ORNEK_BELGE)
        ustveri["belge"]["sayi"] = "E-99999999-000.00-1"
        sonuc = ustveri_belge_tutarliligi(ustveri, ORNEK_BELGE)
        assert sonuc["tutarli"] is False
        farkli = [k["alan"] for k in sonuc["kontroller"] if not k["tutarli"]]
        assert farkli == ["sayi"]

    def test_tarih_farki_yakalanir(self):
        """Belge görüntüsündeki tarih değişirse fark raporlanmalı (m.28/3)."""
        ustveri = uret_ustveri({}, ORNEK_BELGE)
        degisik_belge = ORNEK_BELGE.replace("11.07.2026", "12.07.2026")
        sonuc = ustveri_belge_tutarliligi(ustveri, degisik_belge)
        assert sonuc["tutarli"] is False
        assert any(
            k["alan"] == "belge_tarihi" and not k["tutarli"]
            for k in sonuc["kontroller"]
        )

    def test_gizlilik_farki_yakalanir(self):
        """Damga yalnızca bir tarafta varsa fark raporlanmalı."""
        ustveri = uret_ustveri({}, ORNEK_BELGE)  # damgasız → TSD
        damgali_belge = "GİZLİ\n" + ORNEK_BELGE
        sonuc = ustveri_belge_tutarliligi(ustveri, damgali_belge)
        assert sonuc["tutarli"] is False

    def test_bos_girdiler_cokmez(self):
        """Boş üstveri/belge çökmemeli; iki taraf da boşsa fark yoktur."""
        sonuc = ustveri_belge_tutarliligi({}, "")
        assert isinstance(sonuc["tutarli"], bool)
        # sayi/konu/tarih iki tarafta da yok → tutarlı; guvenlik iki
        # tarafta da damgasız → TSD'ye karşı boş string farkı raporlanır
        alanlar = {k["alan"]: k["tutarli"] for k in sonuc["kontroller"]}
        assert alanlar["sayi"] is True
        assert alanlar["konu"] is True
