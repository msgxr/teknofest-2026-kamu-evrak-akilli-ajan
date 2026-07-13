# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
REST API testleri — gerçek HTTP istekleriyle uçtan uca doğrulama.

Sunucu, testler boyunca ayrı bir thread'de, işletim sisteminin seçtiği
boş bir portta (port=0) çalıştırılır; istekler stdlib urllib ile atılır.
Böylece EBYS entegrasyon sözleşmesi (uçlar, durum kodları, JSON şemaları)
ağ katmanı dahil sınanmış olur.
"""

import json
import threading
import urllib.error
import urllib.request
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api import MAX_GOVDE_BAYT, sunucu_olustur


# ----------------------------------------------------------------------
# Sunucu fikstürü
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_taban():
    """API sunucusunu test portunda başlatır; testler bitince kapatır."""
    sunucu = sunucu_olustur(host="127.0.0.1", port=0)
    thread = threading.Thread(target=sunucu.serve_forever, daemon=True)
    thread.start()
    host, port = sunucu.server_address[0], sunucu.server_address[1]
    yield f"http://{host}:{port}"
    # Teardown: dinlemeyi durdur, soketi kapat, thread'in bitmesini bekle
    sunucu.shutdown()
    sunucu.server_close()
    thread.join(timeout=5)


# ----------------------------------------------------------------------
# İstek yardımcıları
# ----------------------------------------------------------------------


def _get(taban, yol):
    """GET isteği atar; (durum_kodu, json_gövde) döndürür."""
    try:
        with urllib.request.urlopen(taban + yol, timeout=30) as yanit:
            return yanit.status, json.loads(yanit.read().decode("utf-8"))
    except urllib.error.HTTPError as hata:
        return hata.code, json.loads(hata.read().decode("utf-8"))


def _post_ham(taban, yol, govde_bayt):
    """Ham baytlarla POST isteği atar; (durum_kodu, json_gövde) döndürür."""
    istek = urllib.request.Request(
        taban + yol,
        data=govde_bayt,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(istek, timeout=120) as yanit:
            return yanit.status, json.loads(yanit.read().decode("utf-8"))
    except urllib.error.HTTPError as hata:
        return hata.code, json.loads(hata.read().decode("utf-8"))


def _post(taban, yol, veri):
    """JSON gövdeli POST isteği atar; (durum_kodu, json_gövde) döndürür."""
    return _post_ham(taban, yol, json.dumps(veri, ensure_ascii=False).encode("utf-8"))


# Kurgu dilekçe metni (sentetik; gerçek kişi/kurum verisi içermez).
# "10000000146" checksum'ı geçerli, resmî olarak test amaçlı bilinen değerdir.
DILEKCE_METNI = """T.C.
ÖRNEKKENT KAYMAKAMLIĞINA

Konu: Sokak aydınlatması arızası hakkında

Mahallemizdeki sokak lambalarının üç haftadır yanmadığını, akşam
saatlerinde güvenlik endişesi yaşandığını bilgilerinize sunarım.
Arızanın giderilmesi hususunda gereğini arz ederim. 10.02.2026

Mehmet DEMİR
T.C. Kimlik No: 10000000146
Tel: 0532 111 22 33
E-posta: mehmet.demir@ornek.com
Papatya Mah. Gül Sok. No: 5 Örnekkent
"""


# ----------------------------------------------------------------------
# Testler
# ----------------------------------------------------------------------


class TestSaglikVeKataloglar:
    """GET uçları: sağlık ve katalog sözleşmeleri."""

    def test_saglik(self, api_taban):
        """GET /saglik durum, sürüm, backend ve ajan sayısı döndürmeli."""
        kod, veri = _get(api_taban, "/saglik")
        assert kod == 200
        assert veri["durum"] == "calisiyor"
        assert veri["surum"]
        assert veri["llm_backend"]
        assert veri["ajan_sayisi"] >= 11

    def test_birimler(self, api_taban):
        """GET /birimler birim kataloğunu döndürmeli."""
        kod, veri = _get(api_taban, "/birimler")
        assert kod == 200
        assert veri["adet"] == len(veri["birimler"]) > 0
        ilk = veri["birimler"][0]
        assert "kod" in ilk and "ad" in ilk and "aciklama" in ilk

    def test_evrak_turleri(self, api_taban):
        """GET /evrak-turleri tür kataloğunu döndürmeli (dilekçe dahil)."""
        kod, veri = _get(api_taban, "/evrak-turleri")
        assert kod == 200
        kodlar = [t["kod"] for t in veri["evrak_turleri"]]
        assert "dilekce" in kodlar


class TestEvrakIsle:
    """POST /evrak/isle: uçtan uca evrak işleme sözleşmesi."""

    def test_dilekce_isleme(self, api_taban):
        """Dilekçe metni doğru türle sınıflandırılıp tam sonuç dönmeli."""
        kod, veri = _post(
            api_taban, "/evrak/isle", {"metin": DILEKCE_METNI, "mod": "full"}
        )
        assert kod == 200
        assert veri["siniflandirma"]["tur"] == "dilekce"
        # Uçtan uca sözleşme: temel alanlar yanıt gövdesinde bulunmalı
        for alan in ("ozet", "yonlendirme", "yazi_taslagi", "islem_adimlari"):
            assert alan in veri
        assert veri["yonlendirme"].get("birim")

    def test_classify_modu(self, api_taban):
        """classify modunda taslak üretilmemeli, sınıflandırma dönmeli."""
        kod, veri = _post(
            api_taban, "/evrak/isle", {"metin": DILEKCE_METNI, "mod": "classify"}
        )
        assert kod == 200
        assert veri["siniflandirma"]["tur"] == "dilekce"
        assert veri["yazi_taslagi"] == ""

    def test_gecersiz_mod(self, api_taban):
        """Bilinmeyen mod değeri 400 ve Türkçe hata döndürmeli."""
        kod, veri = _post(
            api_taban, "/evrak/isle", {"metin": DILEKCE_METNI, "mod": "yanlis"}
        )
        assert kod == 400
        assert "mod" in veri["hata"]

    def test_metin_eksik(self, api_taban):
        """'metin' alanı yoksa veya boşsa 400 döndürmeli."""
        for govde in ({}, {"metin": ""}, {"metin": 42}):
            kod, veri = _post(api_taban, "/evrak/isle", govde)
            assert kod == 400
            assert "metin" in veri["hata"]


class TestAnonimlestirme:
    """POST /evrak/anonimlestir: KVKK paylaşım nüshası sözleşmesi."""

    def test_kisisel_veriler_maskelenmeli(self, api_taban):
        """T.C. kimlik, telefon ve e-posta anonim nüshada görünmemeli."""
        kod, veri = _post(api_taban, "/evrak/anonimlestir", {"metin": DILEKCE_METNI})
        assert kod == 200
        anonim = veri["anonim_metin"]
        assert anonim
        assert "10000000146" not in anonim
        assert "0532 111 22 33" not in anonim
        assert "mehmet.demir@ornek.com" not in anonim
        rapor = veri["rapor"]
        assert rapor["toplam"] >= 3
        assert rapor["maskelenen"]["tc_kimlik"] >= 1


class TestHataYollari:
    """Hatalı isteklerin durum kodu ve Türkçe mesaj sözleşmesi."""

    def test_gecersiz_json(self, api_taban):
        """Bozuk JSON gövdesi 400 ve Türkçe hata döndürmeli."""
        kod, veri = _post_ham(api_taban, "/evrak/isle", b"{bozuk json!!")
        assert kod == 400
        assert "JSON" in veri["hata"]

    def test_asiri_buyuk_govde(self, api_taban):
        """1 MB sınırını aşan gövde 413 ile reddedilmeli."""
        buyuk = json.dumps({"metin": "A" * (MAX_GOVDE_BAYT + 1000)}).encode("utf-8")
        assert len(buyuk) > MAX_GOVDE_BAYT
        kod, veri = _post_ham(api_taban, "/evrak/isle", buyuk)
        assert kod == 413
        assert "büyük" in veri["hata"]

    def test_bilinmeyen_uc_get(self, api_taban):
        """Bilinmeyen GET ucu 404 döndürmeli."""
        kod, veri = _get(api_taban, "/olmayan-uc")
        assert kod == 404
        assert "Bilinmeyen" in veri["hata"]

    def test_bilinmeyen_uc_post(self, api_taban):
        """Bilinmeyen POST ucu 404 döndürmeli."""
        kod, veri = _post(api_taban, "/evrak/olmayan", {"metin": "deneme"})
        assert kod == 404
        assert "Bilinmeyen" in veri["hata"]
