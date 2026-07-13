# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Evrak Kayıt Defteri (KayitDefteri) ve HTML işlem raporu (uret_html_rapor)
testleri.

Kayıt defteri geçici dizinde (tmp_path) kurulur; kaydet/sorgula/istatistik
akışları, SQL injection ve LIKE joker denemeleri ile pipeline entegrasyonu
(varsayılan kayıt KAPALI — değerlendirme betikleri etkilenmez) doğrulanır.
"""

import sqlite3
import sys
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.islem_raporu import RAPOR_BASLIGI, uret_html_rapor
from src.utils.kayit_defteri import KayitDefteri


def _ornek_sonuc(**degisiklikler) -> dict:
    """Tipik bir pipeline sonucu üretir; alanlar parametreyle ezilebilir."""
    sonuc = {
        "input_file": "data/raw/kurgu_evraklar/dilekce_01.txt",
        "siniflandirma": {"tur": "dilekce", "tur_adi": "Dilekçe", "guven": 0.9},
        "bilgi_cikarim": {"konu": "Su kesintisi hakkında"},
        "eksik_bilgiler": [
            {"alan": "iletisim", "oncelik": "kritik", "aciklama": "İletişim bilgisi yok"},
        ],
        "yonlendirme": {"birim": "Yazı İşleri Müdürlüğü", "birim_kodu": "yazi_isleri", "guven": 0.8},
        "onceliklendirme": {"oncelik": "ivedi", "son_tarih": "2026-07-20"},
        "format_denetimi": {"uygun": True, "skor": 0.95},
        "insan_onayi": {"gerekli": False, "gerekceler": []},
        "ozet": "Su kesintisi nedeniyle mağduriyet bildiren kurgusal dilekçe özeti.",
        "islem_suresi_saniye": 0.42,
    }
    sonuc.update(degisiklikler)
    return sonuc


class TestKaydet:
    """kaydet birim testleri."""

    def test_kaydet_id_dondurur_ve_artar(self, tmp_path):
        """Her kayıt artan bir kimlik almalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        id1 = defter.kaydet(_ornek_sonuc())
        id2 = defter.kaydet(_ornek_sonuc())
        assert isinstance(id1, int)
        assert id2 == id1 + 1

    def test_kaydet_alanlari_dogru_yazar(self, tmp_path):
        """Sonuç alanları ilgili sütunlara doğru aktarılmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_ornek_sonuc())
        kayit = defter.sorgula()[0]
        assert kayit["kaynak"].endswith("dilekce_01.txt")
        assert kayit["tur"] == "dilekce"
        assert kayit["tur_guven"] == 0.9
        assert kayit["birim"] == "Yazı İşleri Müdürlüğü"
        assert kayit["birim_guven"] == 0.8
        assert kayit["oncelik"] == "ivedi"
        assert kayit["son_tarih"] == "2026-07-20"
        assert kayit["eksik_sayisi"] == 1
        assert kayit["kritik_eksik"] == 1
        assert kayit["format_skoru"] == 0.95
        assert kayit["sure_saniye"] == 0.42
        assert kayit["insan_onayi"] == 0
        assert kayit["ozet_ilk_200"].startswith("Su kesintisi")
        assert kayit["zaman"]  # ISO zaman damgası dolu olmalı

    def test_ozet_200_karaktere_kirpilir(self, tmp_path):
        """Uzun özet, kolon adının vadettiği gibi ilk 200 karaktere kırpılmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_ornek_sonuc(ozet="A" * 500))
        kayit = defter.sorgula()[0]
        assert len(kayit["ozet_ilk_200"]) == 200

    def test_bos_ve_bozuk_sonuc_toleransi(self, tmp_path):
        """Boş sözlük ve sözlük olmayan girdi denetim izini koparmamalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        id1 = defter.kaydet({})
        id2 = defter.kaydet("bozuk girdi")  # type: ignore[arg-type]
        assert id2 == id1 + 1
        kayitlar = defter.sorgula()
        assert len(kayitlar) == 2
        assert kayitlar[0]["tur"] == ""
        assert kayitlar[0]["eksik_sayisi"] == 0


class TestSorgula:
    """sorgula birim testleri."""

    def _dolu_defter(self, tmp_path) -> KayitDefteri:
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_ornek_sonuc())
        defter.kaydet(_ornek_sonuc(
            input_file="data/raw/kurgu_evraklar/rapor_02.txt",
            siniflandirma={"tur": "rapor", "tur_adi": "Rapor", "guven": 0.7},
            yonlendirme={"birim": "Bilgi İşlem Müdürlüğü", "guven": 0.6},
            onceliklendirme={"oncelik": "normal"},
            ozet="Sunucu bakımına ilişkin kurgusal rapor özeti (%10 kesinti).",
        ))
        return defter

    def test_tur_filtresi(self, tmp_path):
        defter = self._dolu_defter(tmp_path)
        kayitlar = defter.sorgula(tur="rapor")
        assert len(kayitlar) == 1
        assert kayitlar[0]["tur"] == "rapor"

    def test_birim_ve_oncelik_filtresi(self, tmp_path):
        defter = self._dolu_defter(tmp_path)
        assert len(defter.sorgula(birim="Yazı İşleri Müdürlüğü")) == 1
        assert len(defter.sorgula(oncelik="ivedi")) == 1
        assert len(defter.sorgula(birim="Yazı İşleri Müdürlüğü", oncelik="normal")) == 0

    def test_metin_arama_ozet_ve_kaynakta(self, tmp_path):
        defter = self._dolu_defter(tmp_path)
        assert len(defter.sorgula(metin_ara="Sunucu bakımına")) == 1
        assert len(defter.sorgula(metin_ara="dilekce_01")) == 1  # kaynak alanı
        assert len(defter.sorgula(metin_ara="olmayan metin xyz")) == 0

    def test_siralama_ve_limit(self, tmp_path):
        """En yeni kayıt üstte olmalı; limit uygulanmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        for i in range(5):
            defter.kaydet(_ornek_sonuc(ozet=f"kayıt {i}"))
        kayitlar = defter.sorgula(limit=3)
        assert len(kayitlar) == 3
        assert kayitlar[0]["ozet_ilk_200"] == "kayıt 4"
        # Geçersiz limit değerleri kırpılır/varsayılana döner
        assert len(defter.sorgula(limit=-7)) == 1
        assert len(defter.sorgula(limit="bozuk")) == 5  # type: ignore[arg-type]


class TestGuvenlik:
    """SQL injection ve LIKE joker denemeleri (CWE-89)."""

    def test_sql_injection_denemesi_zararsiz(self, tmp_path):
        """Injection dizgileri tabloyu bozmamalı, veri sızdırmamalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_ornek_sonuc())
        saldiri = "'; DROP TABLE islemler; --"
        # Tüm filtre girdilerinde deneme: istisna yok, eşleşme yok
        assert defter.sorgula(tur=saldiri) == []
        assert defter.sorgula(birim=saldiri) == []
        assert defter.sorgula(oncelik=saldiri) == []
        assert defter.sorgula(metin_ara=saldiri) == []
        # Tablo hâlâ ayakta ve kayıt duruyor
        assert defter.istatistik()["toplam"] == 1

    def test_injection_icerigi_veri_olarak_saklanir(self, tmp_path):
        """Evrak içeriğindeki injection dizgisi düz veri olarak yazılmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        zararli = 'x"; DROP TABLE islemler; --'
        defter.kaydet(_ornek_sonuc(ozet=zararli))
        kayit = defter.sorgula()[0]
        assert kayit["ozet_ilk_200"] == zararli
        assert defter.istatistik()["toplam"] == 1

    def test_like_jokerleri_duz_metin_olarak_aranir(self, tmp_path):
        """% ve _ karakterleri desen değil düz metin olarak aranmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        # Kaynak adları bilinçli olarak joker karakter içermiyor: arama
        # özet VE kaynak alanlarında çalıştığı için sonuçlar sade kalmalı.
        defter.kaydet(_ornek_sonuc(
            input_file="dilekce01.txt", ozet="Bütçede %10 artış öngörülmüştür.",
        ))
        defter.kaydet(_ornek_sonuc(
            input_file="rapor01.txt", ozet="Joker karakter içermeyen özet.",
        ))
        # '%' tek başına her şeyle eşleşmemeli, yalnızca % içeren kayıtla
        assert len(defter.sorgula(metin_ara="%")) == 1
        assert len(defter.sorgula(metin_ara="%10")) == 1
        assert len(defter.sorgula(metin_ara="_")) == 0


class TestIstatistik:
    """istatistik birim testleri."""

    def test_bos_defter(self, tmp_path):
        defter = KayitDefteri(tmp_path / "test.db")
        istatistik = defter.istatistik()
        assert istatistik["toplam"] == 0
        assert istatistik["tur_dagilimi"] == {}
        assert istatistik["birim_dagilimi"] == {}
        assert istatistik["ort_sure_saniye"] == 0.0
        assert istatistik["insan_onayi_sayisi"] == 0
        assert istatistik["kritik_eksikli_sayisi"] == 0

    def test_dagilimlar_ve_ortalama(self, tmp_path):
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_ornek_sonuc(islem_suresi_saniye=0.2))
        defter.kaydet(_ornek_sonuc(islem_suresi_saniye=0.4))
        defter.kaydet(_ornek_sonuc(
            siniflandirma={"tur": "rapor"},
            yonlendirme={"birim": "Bilgi İşlem Müdürlüğü"},
            eksik_bilgiler=[],
            insan_onayi={"gerekli": True, "gerekceler": ["düşük güven"]},
            islem_suresi_saniye=0.6,
        ))
        istatistik = defter.istatistik()
        assert istatistik["toplam"] == 3
        assert istatistik["tur_dagilimi"] == {"dilekce": 2, "rapor": 1}
        assert istatistik["birim_dagilimi"]["Yazı İşleri Müdürlüğü"] == 2
        assert istatistik["oncelik_dagilimi"]["ivedi"] == 3
        assert abs(istatistik["ort_sure_saniye"] - 0.4) < 1e-9
        assert istatistik["insan_onayi_sayisi"] == 1
        assert istatistik["kritik_eksikli_sayisi"] == 2

    def test_kalicilik(self, tmp_path):
        """Aynı dosyaya yeniden bağlanınca kayıtlar korunmalı (denetim izi)."""
        yol = tmp_path / "kalici.db"
        KayitDefteri(yol).kaydet(_ornek_sonuc())
        assert KayitDefteri(yol).istatistik()["toplam"] == 1


class TestPipelineEntegrasyonu:
    """EndToEndPipeline kayıt defteri entegrasyonu."""

    # Sınıflandırılabilir uzunlukta kurgusal dilekçe metni (gerçek veri değildir)
    KURGU_METIN = (
        "Sayın Yetkili,\n\n"
        "Gökpınar Mahallesi'nde 05.07.2026 tarihinden bu yana yaşanan su "
        "kesintisi nedeniyle mağduriyet yaşamaktayım. Konunun incelenerek "
        "tarafıma bilgi verilmesini arz ederim.\n\n"
        "Ayşe Yılmaz"
    )

    def test_varsayilan_kayit_kapali(self):
        """Varsayılan kurulumda defter None olmalı (evaluate.py etkilenmez)."""
        from src.pipelines.end_to_end_pipeline import EndToEndPipeline

        pipeline = EndToEndPipeline()
        assert pipeline.kayit_defteri is None

    def test_kayit_aktif_pipeline_satir_yazar(self, tmp_path):
        """Kayıt aktifken işlenen metin defterde tek satır oluşturmalı."""
        from src.pipelines.end_to_end_pipeline import EndToEndPipeline

        db_yolu = tmp_path / "pipeline.db"
        pipeline = EndToEndPipeline(
            kayit_defteri_aktif=True, kayit_defteri_yolu=str(db_yolu)
        )
        assert pipeline.kayit_defteri is not None

        sonuc = pipeline.process_text(self.KURGU_METIN, source_name="kurgu_dilekce.txt")
        assert sonuc["siniflandirma"]["tur"]  # işlem gerçekten çalıştı

        kayitlar = pipeline.kayit_defteri.sorgula()
        assert len(kayitlar) == 1
        assert kayitlar[0]["kaynak"] == "kurgu_dilekce.txt"
        assert kayitlar[0]["tur"] == sonuc["siniflandirma"]["tur"]

        # Ham dosyada da satır duruyor mu (bağımsız doğrulama)?
        baglanti = sqlite3.connect(str(db_yolu))
        try:
            adet = baglanti.execute("SELECT COUNT(*) FROM islemler").fetchone()[0]
        finally:
            baglanti.close()
        assert adet == 1

    def test_kayit_parametresiyle_kapatilabilir(self, tmp_path):
        """Defter aktifken bile kayit=False çağrısı satır yazmamalı."""
        from src.pipelines.end_to_end_pipeline import EndToEndPipeline

        pipeline = EndToEndPipeline(
            kayit_defteri_aktif=True,
            kayit_defteri_yolu=str(tmp_path / "kapali.db"),
        )
        pipeline.process_text(self.KURGU_METIN, kayit=False)
        assert pipeline.kayit_defteri.istatistik()["toplam"] == 0


class TestIslemRaporu:
    """uret_html_rapor birim testleri."""

    def test_tam_sonucla_temel_bolumler(self):
        """Rapor tüm ana bölümleri ve değerleri içermeli."""
        rapor = uret_html_rapor(_ornek_sonuc(
            mevzuat_eslestirme=[{"baslik": "Resmî Yazışma Yönetmeliği", "benzerlik": 0.8}],
            yazi_taslagi="Sayın İlgili,\n\nGereğini arz ederim.",
            islem_adimlari=[{"agent": "ocr", "description": "OCR", "status": "success", "sure_saniye": 0.01}],
            anonimlestirme={"metin": "maskeli", "rapor": {"toplam": 2, "maskelenen": {"kisi_adlari": 2}}},
        ))
        assert rapor.startswith("<!DOCTYPE html>")
        assert RAPOR_BASLIGI in rapor
        for baslik in [
            "Sınıflandırma", "Çıkarılan Bilgiler", "Eksik Bilgiler",
            "Mevzuat Önerileri", "Özet", "Yazı Taslağı", "Format Denetimi",
            "Birim Yönlendirme", "Önceliklendirme", "KVKK Maskeleme Raporu",
            "İşlem Adımları",
        ]:
            assert baslik in rapor, f"Bölüm eksik: {baslik}"
        assert "Dilekçe" in rapor
        assert "Yazı İşleri Müdürlüğü" in rapor
        assert "Gereğini arz ederim." in rapor

    def test_bos_sonuc_toleransi(self):
        """Boş sözlükle bile geçerli, tam bir HTML belge üretmeli."""
        rapor = uret_html_rapor({})
        assert rapor.startswith("<!DOCTYPE html>")
        assert "</html>" in rapor
        assert RAPOR_BASLIGI in rapor

    def test_html_kacisi_xss(self):
        """Evrak içeriğindeki HTML/betik raporda etkisizleştirilmeli (CWE-79)."""
        zararli = "<script>alert('xss')</script>"
        rapor = uret_html_rapor(_ornek_sonuc(
            ozet=zararli,
            yazi_taslagi=zararli,
            siniflandirma={"tur": "dilekce", "tur_adi": zararli, "guven": 0.5},
        ))
        assert "<script>" not in rapor
        assert "&lt;script&gt;" in rapor


class TestInsanOnayiKuyrugu:
    """İnsan Onayı Kuyruğu için gerekçe sütunu ve filtre testleri (P0-5)."""

    def test_gerekce_kaydedilir(self, tmp_path):
        """insan_onayi.gerekceler '; ' ile birleştirilip saklanmalı."""
        defter = KayitDefteri(tmp_path / "defter.db")
        defter.kaydet(_ornek_sonuc(insan_onayi={
            "gerekli": True,
            "gerekceler": ["Sınıflandırma güveni düşük (0.45)",
                           "Gizlilik dereceli evrak (Yön. m.25)"],
        }))
        kayit = defter.sorgula(limit=1)[0]
        assert kayit["insan_onayi"] == 1
        assert "0.45" in kayit["insan_onayi_gerekce"]
        assert "m.25" in kayit["insan_onayi_gerekce"]

    def test_insan_onayi_filtresi(self, tmp_path):
        """sorgula(insan_onayi=True) yalnızca onay bekleyenleri döndürmeli."""
        defter = KayitDefteri(tmp_path / "defter.db")
        defter.kaydet(_ornek_sonuc())  # gerekli=False
        defter.kaydet(_ornek_sonuc(insan_onayi={
            "gerekli": True, "gerekceler": ["düşük güven"],
        }))
        bekleyen = defter.sorgula(insan_onayi=True)
        digerleri = defter.sorgula(insan_onayi=False)
        assert len(bekleyen) == 1 and bekleyen[0]["insan_onayi"] == 1
        assert len(digerleri) == 1 and digerleri[0]["insan_onayi"] == 0

    def test_eski_semadan_gecis(self, tmp_path):
        """Gerekçe sütunu olmayan eski defter açılışta genişletilmeli."""
        import sqlite3

        yol = tmp_path / "eski.db"
        baglanti = sqlite3.connect(yol)
        baglanti.execute(
            "CREATE TABLE islemler (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "zaman TEXT NOT NULL, kaynak TEXT, tur TEXT, tur_guven REAL, "
            "birim TEXT, birim_guven REAL, oncelik TEXT, son_tarih TEXT, "
            "eksik_sayisi INTEGER, kritik_eksik INTEGER, format_skoru REAL, "
            "sure_saniye REAL, insan_onayi INTEGER, ozet_ilk_200 TEXT)"
        )
        baglanti.commit()
        baglanti.close()

        defter = KayitDefteri(yol)
        defter.kaydet(_ornek_sonuc(insan_onayi={
            "gerekli": True, "gerekceler": ["göç testi"],
        }))
        kayit = defter.sorgula(insan_onayi=True, limit=1)[0]
        assert kayit["insan_onayi_gerekce"] == "göç testi"
