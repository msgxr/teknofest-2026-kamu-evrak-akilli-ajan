"""
Evrak İlişki Zinciri (zincir_kur) ve kalibrasyon özetleme testleri.

Sahte pipeline sonuç sözlükleriyle çalışır: ilgi referansı bağı, konu
benzerliği bağı, bağımsız evraklar, boş/tek elemanlı liste ve üç evraklı
bağlı bileşen (A→B→C) senaryolarını doğrular. Ayrıca kalibrasyon
betiğinin saf desen-özetleme/öneri fonksiyonlarını sahte JSONL
satırlarıyla test eder — pipeline veya dosya sistemi gerektirmez.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kalibrasyon_onerisi import desenleri_ozetle, oneri_uret
from src.utils.iliski_zinciri import zincir_kur
from src.utils.kokpit import kokpit_iliskiler


def _sonuc(ad: str, **bilgi) -> dict:
    """input_file + bilgi_cikarim alanlı sahte pipeline sonucu üretir."""
    varsayilan = {
        "evrak_sayisi": "",
        "referans_numaralari": [],
        "ilgi_referanslari": [],
        "konu": "",
        "muhatap": "",
        "kurum_adlari": [],
    }
    varsayilan.update(bilgi)
    return {"input_file": ad, "bilgi_cikarim": varsayilan}


class TestZincirKur:
    """zincir_kur birim testleri."""

    def test_ilgi_referansi_bagi(self):
        """Bir evrakın sayısı diğerinin ilgisinde geçiyorsa güçlü bağ kurulmalı."""
        dilekce = _sonuc(
            "dilekce_a.txt",
            evrak_sayisi="2026/1893",
            konu="Park aydınlatma arızası hakkında",
        )
        cevap = _sonuc(
            "cevap_a.txt",
            evrak_sayisi="E-91435276-622.03-2026/507",
            ilgi_referanslari=["22/06/2026 tarihli ve 2026/1893 kayıt sayılı başvurunuz"],
            konu="Bilgi edinme başvurunuz hakkında",
        )
        sonuc = zincir_kur([dilekce, cevap])
        assert len(sonuc["zincirler"]) == 1
        zincir = sonuc["zincirler"][0]
        assert zincir["evraklar"] == ["dilekce_a.txt", "cevap_a.txt"]
        assert zincir["baglanti_turu"] == "ilgi_referansi"
        assert "2026/1893" in zincir["aciklama"]
        assert sonuc["bagimsiz"] == []

    def test_konu_benzerligi_ayni_muhatap(self):
        """Benzer konu + aynı muhatap orta güçte bağ kurmalı."""
        a = _sonuc(
            "dilekce_b.txt",
            konu="Emlak vergisi iadesi talebi",
            muhatap="AKÇOVA BELEDİYE BAŞKANLIĞINA",
        )
        b = _sonuc(
            "hatirlatma_b.txt",
            konu="Emlak vergisi iadesi talebi hatırlatması",
            muhatap="AKÇOVA BELEDİYE BAŞKANLIĞINA",
        )
        sonuc = zincir_kur([a, b])
        assert len(sonuc["zincirler"]) == 1
        zincir = sonuc["zincirler"][0]
        assert zincir["baglanti_turu"] == "konu_benzerligi"
        assert set(zincir["evraklar"]) == {"dilekce_b.txt", "hatirlatma_b.txt"}

    def test_konu_benzer_ama_taraf_farkli_bag_yok(self):
        """Konu benzese de taraflar ayrıysa bağ kurulmamalı (sahte bağ önlemi)."""
        a = _sonuc(
            "dilekce_c.txt",
            konu="Su kesintisi arızası bildirimi",
            muhatap="GÖKPINAR BELEDİYE BAŞKANLIĞINA",
        )
        b = _sonuc(
            "dilekce_d.txt",
            konu="Su kesintisi arızası bildirimi",
            muhatap="SARIVELİ KAYMAKAMLIĞINA",
        )
        sonuc = zincir_kur([a, b])
        assert sonuc["zincirler"] == []
        assert sonuc["bagimsiz"] == ["dilekce_c.txt", "dilekce_d.txt"]

    def test_bagimsiz_evraklar(self):
        """Hiçbir sinyal paylaşmayan evraklar bağımsız listelenmeli."""
        sonuc = zincir_kur(
            [
                _sonuc("rapor_x.txt", konu="Yıllık denetim raporu"),
                _sonuc("genelge_y.txt", konu="Enerji tasarrufu tedbirleri"),
                _sonuc("tutanak_z.txt", konu="Teslim tesellüm işlemi"),
            ]
        )
        assert sonuc["zincirler"] == []
        assert sonuc["bagimsiz"] == ["rapor_x.txt", "genelge_y.txt", "tutanak_z.txt"]

    def test_bos_liste(self):
        """Boş liste çökme olmadan boş sonuç üretmeli."""
        sonuc = zincir_kur([])
        assert sonuc == {"zincirler": [], "bagimsiz": []}

    def test_tek_evrak(self):
        """Tek evrak kendi kendine zincir kuramaz; bağımsız olmalı."""
        sonuc = zincir_kur([_sonuc("dilekce_tek.txt", evrak_sayisi="2026/42731")])
        assert sonuc["zincirler"] == []
        assert sonuc["bagimsiz"] == ["dilekce_tek.txt"]

    def test_uc_evrakli_zincir_bagli_bilesen(self):
        """A→B→C ilgi bağları tek bağlı bileşende (üç evraklı zincir) birleşmeli."""
        a = _sonuc("dilekce_e.txt", evrak_sayisi="2026/1502")
        b = _sonuc(
            "cevap_e.txt",
            evrak_sayisi="E-30268157-903.07-2026/2241",
            ilgi_referanslari=["12/06/2026 tarihli ve 2026/1502 kayıt sayılı dilekçeniz"],
        )
        c = _sonuc(
            "itiraz_e.txt",
            evrak_sayisi="2026/1777",
            ilgi_referanslari=[
                "01/07/2026 tarihli ve E-30268157-903.07-2026/2241 sayılı yazınız"
            ],
        )
        sonuc = zincir_kur([a, b, c])
        assert len(sonuc["zincirler"]) == 1
        zincir = sonuc["zincirler"][0]
        assert zincir["evraklar"] == ["dilekce_e.txt", "cevap_e.txt", "itiraz_e.txt"]
        assert zincir["baglanti_turu"] == "ilgi_referansi"
        assert sonuc["bagimsiz"] == []

    def test_kisa_numara_ve_yil_sahte_bag_kurmaz(self):
        """Kısa numaralar ve yalın yıl ('2026') ilgi eşleşmesine aday olmamalı."""
        a = _sonuc("dilekce_f.txt", evrak_sayisi="2026", referans_numaralari=["884"])
        b = _sonuc(
            "cevap_f.txt",
            ilgi_referanslari=["15/06/2026 tarihli ve 2026/884 sayılı yazı"],
        )
        sonuc = zincir_kur([a, b])
        assert sonuc["zincirler"] == []
        assert set(sonuc["bagimsiz"]) == {"dilekce_f.txt", "cevap_f.txt"}

    def test_bozuk_kayitlara_tolerans(self):
        """Sözlük olmayan/eksik anahtarlı kayıtlar raporu düşürmemeli."""
        sonuc = zincir_kur([None, {"input_file": "yalniz.txt"}, "bozuk"])
        assert sonuc["zincirler"] == []
        assert len(sonuc["bagimsiz"]) == 3
        assert "yalniz.txt" in sonuc["bagimsiz"]

    def test_kokpit_iliskiler_ayni_sonucu_verir(self):
        """kokpit_iliskiler, zincir_kur ile aynı sözleşmeyi döndürmeli."""
        girdiler = [
            _sonuc("dilekce_g.txt", evrak_sayisi="2026/3333"),
            _sonuc(
                "cevap_g.txt",
                ilgi_referanslari=["tarihli ve 2026/3333 kayıt sayılı başvurunuz"],
            ),
        ]
        assert kokpit_iliskiler(girdiler) == zincir_kur(girdiler)


class TestKalibrasyonDesenleri:
    """kalibrasyon_onerisi saf fonksiyon testleri (sahte JSONL satırları)."""

    def _satir(self, tahmin_tur, dogru_tur, tahmin_birim, dogru_birim) -> dict:
        return {
            "zaman": "2026-07-11T09:00:00",
            "dosya": "data/raw/kurgu_evraklar/ornek.txt",
            "tahmin_tur": tahmin_tur,
            "dogru_tur": dogru_tur,
            "tahmin_birim": tahmin_birim,
            "dogru_birim": dogru_birim,
        }

    def test_desen_sayimi_ve_siralama(self):
        """Tür/birim düzeltmeleri desen bazında sayılmalı; onaylar ayrılmalı."""
        satirlar = [
            self._satir("dilekce", "cevap_yazisi", "yazi_isleri", "yazi_isleri"),
            self._satir("dilekce", "cevap_yazisi", "yazi_isleri", "hukuk"),
            self._satir("dilekce", "cevap_yazisi", "hukuk", "hukuk"),
            self._satir("rapor", "tutanak", "mali_hizmetler", "mali_hizmetler"),
            self._satir("dilekce", "dilekce", "hukuk", "hukuk"),  # tam onay
        ]
        ozet = desenleri_ozetle(satirlar)
        assert ozet["toplam_satir"] == 5
        assert ozet["onay_sayisi"] == 1
        # En sık desen önce gelmeli
        assert ozet["tur_desenleri"][0] == {
            "tahmin": "dilekce",
            "dogru": "cevap_yazisi",
            "adet": 3,
        }
        assert ozet["tur_desenleri"][1] == {
            "tahmin": "rapor",
            "dogru": "tutanak",
            "adet": 1,
        }
        assert ozet["birim_desenleri"] == [
            {"tahmin": "yazi_isleri", "dogru": "hukuk", "adet": 1}
        ]

    def test_oneri_metinleri_somut_referansli(self):
        """Öneriler ilgili dosya/sözlük adlarını ve kanıt düzeyini içermeli."""
        ozet = desenleri_ozetle(
            [
                self._satir("dilekce", "cevap_yazisi", "yazi_isleri", "hukuk"),
                self._satir("dilekce", "cevap_yazisi", "yazi_isleri", "hukuk"),
                self._satir("dilekce", "cevap_yazisi", "yazi_isleri", "hukuk"),
            ]
        )
        oneriler = oneri_uret(ozet)
        assert len(oneriler) == 2  # bir tür + bir birim deseni

        tur_onerisi = next(o for o in oneriler if o["kapsam"] == "tur")
        assert tur_onerisi["desen"] == "dilekce → cevap_yazisi"
        assert tur_onerisi["adet"] == 3
        assert tur_onerisi["kanit_duzeyi"] == "güçlü"
        assert "AGIRLIKLI_KELIMELER['cevap_yazisi']" in tur_onerisi["oneri"]
        assert "classification_agent.py" in tur_onerisi["oneri"]

        birim_onerisi = next(o for o in oneriler if o["kapsam"] == "birim")
        assert "BIRIMLER['hukuk']['anahtar_kelimeler']" in birim_onerisi["oneri"]
        assert "routing_agent.py" in birim_onerisi["oneri"]

    def test_bos_ve_bozuk_satirlar(self):
        """Boş liste ve bozuk kayıtlar güvenle özetlenmeli."""
        assert desenleri_ozetle([]) == {
            "toplam_satir": 0,
            "onay_sayisi": 0,
            "tur_desenleri": [],
            "birim_desenleri": [],
        }
        ozet = desenleri_ozetle([None, "bozuk", {}])  # type: ignore[list-item]
        assert ozet["tur_desenleri"] == []
        assert oneri_uret(ozet) == []
