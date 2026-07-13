# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Kurum Kokpiti (kokpit_ozeti) ve e-Yazışma üstverisi (uret_ustveri) testleri.

Sahte pipeline sonuç sözlükleriyle çalışır; boş liste ve eksik anahtar
toleransı dahil sınır durumları doğrular.
"""

import sys
from datetime import date
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.eyazisma import KAYNAK_SISTEM, USTVERI_SURUMU, uret_ustveri
from src.utils.kokpit import MANUEL_ISLEM_DAKIKA_VARSAYIMI, kokpit_ozeti


def _ornek_sonuc(**degisiklikler) -> dict:
    """Tipik bir pipeline sonucu üretir; alanlar parametreyle ezilebilir."""
    sonuc = {
        "input_file": "data/raw/kurgu_evraklar/dilekce_01.txt",
        "siniflandirma": {"tur": "dilekce", "tur_adi": "Dilekçe", "guven": 0.9},
        "bilgi_cikarim": {
            "konu": "Su kesintisi hakkında",
            "muhatap": "Gökpınar Belediye Başkanlığı",
            "ilgi_referanslari": ["a) 12.05.2026 tarihli dilekçe"],
            "dagitim_birimleri": ["Yazı İşleri Müdürlüğü"],
        },
        "eksik_bilgiler": [],
        "yonlendirme": {"birim": "Yazı İşleri Müdürlüğü", "birim_kodu": "yazi_isleri", "guven": 0.8},
        "insan_onayi": {"gerekli": False, "gerekceler": []},
        "islem_suresi_saniye": 0.5,
    }
    sonuc.update(degisiklikler)
    return sonuc


class TestKokpitOzeti:
    """kokpit_ozeti birim testleri."""

    def test_bos_liste(self):
        """Boş listeyle çökme olmadan sıfır göstergeler üretmeli."""
        ozet = kokpit_ozeti([])
        assert ozet["evrak_sayisi"] == 0
        assert ozet["tur_dagilimi"] == {}
        assert ozet["birim_dagilimi"] == {}
        assert ozet["eksikli_evrak_orani"] == 0.0
        assert ozet["kritik_eksikli_sayisi"] == 0
        assert ozet["ort_islem_suresi_sn"] == 0.0
        assert ozet["toplam_islem_suresi_sn"] == 0.0
        assert ozet["dusuk_guvenli_sayisi"] == 0
        assert ozet["tahmini_tasarruf"]["tasarruf_orani"] == 0.0

    def test_temel_sayimlar(self):
        """Tür ve birim dağılımları doğru sayılmalı."""
        sonuclar = [
            _ornek_sonuc(),
            _ornek_sonuc(siniflandirma={"tur": "rapor", "tur_adi": "Rapor"}),
            _ornek_sonuc(),
        ]
        ozet = kokpit_ozeti(sonuclar)
        assert ozet["evrak_sayisi"] == 3
        assert ozet["tur_dagilimi"] == {"Dilekçe": 2, "Rapor": 1}
        assert ozet["birim_dagilimi"] == {"Yazı İşleri Müdürlüğü": 3}

    def test_eksikli_oran_ve_kritik(self):
        """Eksikli evrak oranı ve kritik eksik sayısı doğru hesaplanmalı."""
        sonuclar = [
            _ornek_sonuc(eksik_bilgiler=[{"alan": "adres", "oncelik": "kritik"}]),
            _ornek_sonuc(eksik_bilgiler=[{"alan": "tarih", "oncelik": "bilgi"}]),
            _ornek_sonuc(eksik_bilgiler=[]),
            _ornek_sonuc(eksik_bilgiler=[]),
        ]
        ozet = kokpit_ozeti(sonuclar)
        assert ozet["eksikli_evrak_orani"] == 0.5
        assert ozet["kritik_eksikli_sayisi"] == 1

    def test_sure_ve_tasarruf(self):
        """Süre toplamı/ortalaması ve tahmini tasarruf tutarlı olmalı."""
        sonuclar = [
            _ornek_sonuc(islem_suresi_saniye=1.0),
            _ornek_sonuc(islem_suresi_saniye=3.0),
        ]
        ozet = kokpit_ozeti(sonuclar)
        assert ozet["toplam_islem_suresi_sn"] == 4.0
        assert ozet["ort_islem_suresi_sn"] == 2.0

        tasarruf = ozet["tahmini_tasarruf"]
        assert tasarruf["manuel_dakika_varsayimi"] == MANUEL_ISLEM_DAKIKA_VARSAYIMI
        beklenen_saat = 2 * MANUEL_ISLEM_DAKIKA_VARSAYIMI / 60.0
        assert tasarruf["manuel_toplam_saat"] == round(beklenen_saat, 2)
        assert tasarruf["sistem_toplam_saniye"] == 4.0
        # 4 sn işlem, 24 dk manuel varsayım → tasarruf 0-1 aralığında ve yüksek
        assert 0.9 < tasarruf["tasarruf_orani"] <= 1.0

    def test_dusuk_guvenli_sayisi(self):
        """insan_onayi.gerekli işaretli evraklar sayılmalı."""
        sonuclar = [
            _ornek_sonuc(insan_onayi={"gerekli": True, "gerekceler": ["düşük güven"]}),
            _ornek_sonuc(insan_onayi={"gerekli": False}),
            _ornek_sonuc(),
        ]
        assert kokpit_ozeti(sonuclar)["dusuk_guvenli_sayisi"] == 1

    def test_eksik_anahtar_toleransi(self):
        """Boş/bozuk kayıtlar çökme olmadan makul değerlere düşmeli."""
        sonuclar = [{}, {"siniflandirma": None, "islem_suresi_saniye": "hatalı"}]
        ozet = kokpit_ozeti(sonuclar)
        assert ozet["evrak_sayisi"] == 2
        assert ozet["tur_dagilimi"] == {"Bilinmiyor": 2}
        assert ozet["birim_dagilimi"] == {"Belirsiz": 2}
        assert ozet["toplam_islem_suresi_sn"] == 0.0
        assert ozet["kritik_eksikli_sayisi"] == 0


class TestUretUstveri:
    """uret_ustveri birim testleri."""

    def test_temel_alanlar(self):
        """Dolu sonuçtan tüm üstveri alanları doğru üretilmeli."""
        ustveri = uret_ustveri(_ornek_sonuc())
        assert ustveri["ustveri_surumu"] == USTVERI_SURUMU
        assert ustveri["kaynak_sistem"] == KAYNAK_SISTEM
        assert ustveri["belge"]["konu"] == "Su kesintisi hakkında"
        assert ustveri["belge"]["tur"] == "dilekce"
        assert ustveri["belge"]["tur_adi"] == "Dilekçe"
        assert ustveri["belge"]["guvenlik_kodu"] == "TSD"
        assert ustveri["belge"]["olusturma_tarihi"] == date.today().isoformat()
        assert ustveri["muhatap"] == {
            "ad": "Gökpınar Belediye Başkanlığı",
            "belirlendi": True,
        }
        assert ustveri["ilgi_listesi"] == ["a) 12.05.2026 tarihli dilekçe"]
        assert ustveri["dagitim"] == ["Yazı İşleri Müdürlüğü"]
        assert ustveri["yonlendirme"] == {
            "birim": "Yazı İşleri Müdürlüğü",
            "birim_kodu": "yazi_isleri",
            "guven": 0.8,
        }

    def test_ivedilik_onceliklendirmeden(self):
        """Önceliklendirme sonucu varsa ivedilik oradan alınmalı."""
        sonuc = _ornek_sonuc(onceliklendirme={"oncelik": "ivedi", "son_tarih": "2026-07-20"})
        assert uret_ustveri(sonuc)["belge"]["ivedilik"] == "ivedi"

    def test_ivedilik_varsayilani_normal(self):
        """Önceliklendirme yoksa ivedilik 'normal' olmalı."""
        assert uret_ustveri(_ornek_sonuc())["belge"]["ivedilik"] == "normal"

    def test_eksik_alanlar_listesi(self):
        """eksik_bilgiler kayıtlarından alan adları toplanmalı."""
        sonuc = _ornek_sonuc(eksik_bilgiler=[
            {"alan": "adres", "oncelik": "kritik"},
            {"aciklama": "alan adı yok"},  # alan anahtarı yok → atlanır
            "serbest metin eksik",
        ])
        assert uret_ustveri(sonuc)["eksik_alanlar"] == ["adres", "serbest metin eksik"]

    def test_bos_sozluk_toleransi(self):
        """Boş sonuç sözlüğünden bile geçerli taslak üretmeli."""
        ustveri = uret_ustveri({})
        assert ustveri["ustveri_surumu"] == USTVERI_SURUMU
        assert ustveri["belge"]["konu"] == ""
        assert ustveri["belge"]["ivedilik"] == "normal"
        assert ustveri["muhatap"] == {"ad": "", "belirlendi": False}
        assert ustveri["ilgi_listesi"] == []
        assert ustveri["dagitim"] == []
        assert ustveri["eksik_alanlar"] == []

    def test_sozluk_disi_girdi_toleransi(self):
        """Sözlük olmayan girdi/bozuk alt alanlar çökmeye yol açmamalı."""
        assert uret_ustveri(None)["belge"]["tur"] == ""  # type: ignore[arg-type]
        sonuc = _ornek_sonuc(
            bilgi_cikarim="bozuk",
            yonlendirme=None,
            onceliklendirme="bozuk",
            eksik_bilgiler=None,
        )
        ustveri = uret_ustveri(sonuc)
        assert ustveri["muhatap"]["belirlendi"] is False
        assert ustveri["yonlendirme"] == {"birim": "", "birim_kodu": "", "guven": None}
        assert ustveri["belge"]["ivedilik"] == "normal"


class TestParametrikTasarruf:
    """Kokpit tasarruf hesabının parametrik manuel süre testleri (P2-11)."""

    def test_varsayilan_varsayim_isaretli(self):
        """Parametre verilmezse varsayılan kullanılmalı ve varsayım işaretlenmeli."""
        ozet = kokpit_ozeti([_ornek_sonuc()])
        t = ozet["tahmini_tasarruf"]
        assert t["manuel_dakika_varsayimi"] == MANUEL_ISLEM_DAKIKA_VARSAYIMI
        assert t["varsayim_mi"] is True

    def test_kurum_olcumu_kullanilir(self):
        """Verilen kurum ölçümü hesaba girmeli ve varsayım işareti kalkmalı."""
        ozet = kokpit_ozeti([_ornek_sonuc()], manuel_dakika=20)
        t = ozet["tahmini_tasarruf"]
        assert t["manuel_dakika_varsayimi"] == 20
        assert t["varsayim_mi"] is False
        assert abs(t["manuel_toplam_saat"] - 20 / 60.0) < 0.01

    def test_gecersiz_deger_varsayilana_duser(self):
        """Sıfır/negatif/bozuk değerde varsayılana dönülmeli (çökme yok)."""
        for bozuk in (0, -5, "abc", None):
            t = kokpit_ozeti([_ornek_sonuc()], manuel_dakika=bozuk)["tahmini_tasarruf"]
            assert t["manuel_dakika_varsayimi"] == MANUEL_ISLEM_DAKIKA_VARSAYIMI
            assert t["varsayim_mi"] is True
