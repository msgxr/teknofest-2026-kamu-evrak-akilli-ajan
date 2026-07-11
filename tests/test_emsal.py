"""
Emsal Evrak Arama (EmsalArama / emsal_ara) ve kayıt defteri şema
genişletmesi (migration) testleri.

Kayıt defteri geçici dizinde (tmp_path) kurulur; kaydet→ara akışı,
benzerlik sıralaması, kendini eleme, eski şemadan geçiş (ALTER TABLE
migration), boş defter ve limit davranışları doğrulanır. Tüm evrak
metinleri kurgusaldır (gerçek kişi/kurum verisi içermez).
"""

import sqlite3
import sys
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.emsal import ASGARI_BENZERLIK, EmsalArama, emsal_ara
from src.utils.kayit_defteri import METIN_OZU_KARAKTER, KayitDefteri

# ---------------------------------------------------------------------------
# Kurgusal evrak metinleri (üç ayrı konu: su kesintisi, sunucu bakımı, atama)
# ---------------------------------------------------------------------------

DILEKCE_SU = (
    "Sayın Yetkili,\n\n"
    "Gökpınar Mahallesi'nde 05.07.2026 tarihinden bu yana yaşanan su "
    "kesintisi nedeniyle mağduriyet yaşamaktayım. Su kesintisinin ivedilikle "
    "giderilmesini ve tarafıma yazılı bilgi verilmesini arz ederim.\n\n"
    "Ayşe Yılmaz"
)

RAPOR_SUNUCU = (
    "Bilgi İşlem Müdürlüğü sunucu bakım raporudur. Veri merkezindeki ana "
    "sunucunun disk değişimi tamamlanmış, yedekleme sistemleri test edilmiş "
    "ve bakım penceresi boyunca hizmetlerde planlı yavaşlama gözlenmiştir."
)

ONAY_ATAMA = (
    "İnsan Kaynakları Müdürlüğünde münhal bulunan veri hazırlama kontrol "
    "işletmeni kadrosuna Mehmet Demir'in atanması hususunu onaylarınıza "
    "arz ederim. Atama işleminin ilgili mevzuata uygun olduğu görülmüştür."
)

# DILEKCE_SU ile aynı konuda, farklı sözcüklerle yazılmış sorgu dilekçesi
SORGU_SU = (
    "Mahallemizde günlerdir devam eden su kesintisi hakkında bilgi almak "
    "istiyorum. Su kesintisi ne zaman giderilecek? Mağduriyetimizin "
    "giderilmesini arz ederim."
)

# Defter dağarcığında hiçbir sözcüğü bulunmayan alakasız sorgu
SORGU_ALAKASIZ = "Uzay istasyonundaki yörünge mekiğinin fırlatma rampası."


def _sonuc(kaynak: str, tur: str = "dilekce", **degisiklikler) -> dict:
    """Tipik bir pipeline sonucu üretir; alanlar parametreyle ezilebilir."""
    sonuc = {
        "input_file": kaynak,
        "siniflandirma": {"tur": tur, "guven": 0.9},
        "yonlendirme": {"birim": "Yazı İşleri Müdürlüğü", "guven": 0.8},
        "onceliklendirme": {"oncelik": "normal"},
        "insan_onayi": {"gerekli": False},
        "ozet": f"{kaynak} için kurgusal özet.",
        "yazi_turu": "cevap_yazisi",
        "islem_suresi_saniye": 0.1,
    }
    sonuc.update(degisiklikler)
    return sonuc


def _dolu_defter(tmp_path) -> KayitDefteri:
    """Üç ayrı konuda kayıt içeren geçici defter kurar."""
    defter = KayitDefteri(tmp_path / "emsal.db")
    defter.kaydet(_sonuc("dilekce_su.txt", "dilekce"), metin=DILEKCE_SU)
    defter.kaydet(_sonuc("rapor_sunucu.txt", "rapor"), metin=RAPOR_SUNUCU)
    defter.kaydet(_sonuc("onay_atama.txt", "onayli_belge"), metin=ONAY_ATAMA)
    return defter


# Emsal modülünün kullandığı sütunlar eklenmeden ÖNCEKİ islemler şeması;
# migration testleri bu şemayı elle kurup yeni sürümle açar.
_ESKI_TABLO_SQL = """
CREATE TABLE islemler (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman         TEXT NOT NULL,
    kaynak        TEXT,
    tur           TEXT,
    tur_guven     REAL,
    birim         TEXT,
    birim_guven   REAL,
    oncelik       TEXT,
    son_tarih     TEXT,
    eksik_sayisi  INTEGER,
    kritik_eksik  INTEGER,
    format_skoru  REAL,
    sure_saniye   REAL,
    insan_onayi   INTEGER,
    ozet_ilk_200  TEXT
)
"""


def _eski_semali_db(yol) -> None:
    """Eski şemalı bir kayıt defteri dosyası ve tek eski kayıt oluşturur."""
    baglanti = sqlite3.connect(str(yol))
    try:
        baglanti.execute(_ESKI_TABLO_SQL)
        baglanti.execute(
            """
            INSERT INTO islemler (
                zaman, kaynak, tur, tur_guven, birim, birim_guven, oncelik,
                son_tarih, eksik_sayisi, kritik_eksik, format_skoru,
                sure_saniye, insan_onayi, ozet_ilk_200
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-01-05T09:00:00", "eski_dilekce.txt", "dilekce", 0.8,
                "Yazı İşleri Müdürlüğü", 0.7, "normal", None, 0, 0, 0.9,
                0.3, 0, "Su kesintisi mağduriyeti bildiren eski kurgusal dilekçe özeti.",
            ),
        )
        baglanti.commit()
    finally:
        baglanti.close()


class TestKaydetYeniAlanlar:
    """kaydet() metin/yazi_turu genişletmesi (geriye uyumluluk dahil)."""

    def test_metin_ozu_ve_yazi_turu_yazilir(self, tmp_path):
        """metin parametresi kırpılarak, yazı türü sonuçtan yazılmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_sonuc("dilekce_su.txt"), metin="  " + DILEKCE_SU + "  ")
        kayit = defter.tum_kayitlar_emsal_icin()[0]
        assert kayit["metin_ozu"] == DILEKCE_SU
        assert kayit["yazi_turu"] == "cevap_yazisi"

    def test_metin_2000_karaktere_kirpilir(self, tmp_path):
        """Metin özü, sabitin vadettiği karakter sayısına kırpılmalı."""
        defter = KayitDefteri(tmp_path / "test.db")
        defter.kaydet(_sonuc("uzun.txt"), metin="A" * (METIN_OZU_KARAKTER + 500))
        kayit = defter.tum_kayitlar_emsal_icin()[0]
        assert len(kayit["metin_ozu"]) == METIN_OZU_KARAKTER

    def test_metinsiz_eski_cagri_kirilmaz(self, tmp_path):
        """Mevcut kaydet(sonuc) çağrıları aynen çalışmalı (boş öz yazılır)."""
        defter = KayitDefteri(tmp_path / "test.db")
        kayit_no = defter.kaydet(_sonuc("eski_cagri.txt"))
        assert isinstance(kayit_no, int)
        kayit = defter.tum_kayitlar_emsal_icin()[0]
        assert kayit["metin_ozu"] == ""


class TestEmsalArama:
    """emsal_ara / EmsalArama davranış testleri."""

    def test_benzer_evrak_ustte(self, tmp_path):
        """Su kesintisi sorgusu, su kesintisi dilekçesini ilk sırada bulmalı."""
        defter = _dolu_defter(tmp_path)
        sonuclar = emsal_ara(SORGU_SU, kayit_defteri=defter)
        assert sonuclar, "Benzer kayıt varken sonuç boş olmamalı"
        assert sonuclar[0]["kaynak"] == "dilekce_su.txt"
        assert sonuclar[0]["tur"] == "dilekce"
        assert sonuclar[0]["tur_adi"] == "Dilekçe"
        assert sonuclar[0]["birim"] == "Yazı İşleri Müdürlüğü"
        assert sonuclar[0]["yazi_turu"] == "cevap_yazisi"
        assert sonuclar[0]["ozet"].startswith("dilekce_su.txt")

    def test_benzerlik_mutlak_ve_sirali(self, tmp_path):
        """Benzerlik 0-1 aralığında ve azalan sıralı olmalı (şişirme yok)."""
        defter = _dolu_defter(tmp_path)
        sonuclar = emsal_ara(SORGU_SU, limit=10, kayit_defteri=defter)
        benzerlikler = [s["benzerlik"] for s in sonuclar]
        assert all(0.0 < b <= 1.0 for b in benzerlikler)
        assert benzerlikler == sorted(benzerlikler, reverse=True)
        # Kısmen örtüşen bir sorgu tam benzerlik iddia etmemeli
        assert benzerlikler[0] < 1.0

    def test_alakasiz_sorgu_bos_veya_dusuk(self, tmp_path):
        """Dağarcık dışı sorgu boş dönmeli (veya ancak çok düşük benzerlik)."""
        defter = _dolu_defter(tmp_path)
        sonuclar = emsal_ara(SORGU_ALAKASIZ, kayit_defteri=defter)
        assert sonuclar == [] or max(s["benzerlik"] for s in sonuclar) < 0.3

    def test_kendini_eleme_metin_ozu(self, tmp_path):
        """Aynı metinle aranınca evrakın kendi kaydı sonuçlara girmemeli."""
        defter = _dolu_defter(tmp_path)
        sonuclar = emsal_ara(DILEKCE_SU, limit=10, kayit_defteri=defter)
        assert all(s["kaynak"] != "dilekce_su.txt" for s in sonuclar)

    def test_kendini_eleme_haric_kaynak(self, tmp_path):
        """haric_kaynak verilen kaynak adı sonuçlardan dışlanmalı."""
        defter = _dolu_defter(tmp_path)
        sonuclar = emsal_ara(
            SORGU_SU, limit=10, kayit_defteri=defter,
            haric_kaynak="dilekce_su.txt",
        )
        assert all(s["kaynak"] != "dilekce_su.txt" for s in sonuclar)

    def test_ayni_kaynak_sonuclarda_tek_gorunur(self, tmp_path):
        """Aynı dosyanın tekrar kayıtları listeyi kopyayla doldurmamalı."""
        defter = _dolu_defter(tmp_path)
        # Aynı dosya küçük bir farkla yeniden işlenmiş olsun
        defter.kaydet(
            _sonuc("dilekce_su.txt"), metin=DILEKCE_SU + " Ek: konu takiptedir."
        )
        sonuclar = emsal_ara(SORGU_SU, limit=10, kayit_defteri=defter)
        kaynaklar = [s["kaynak"] for s in sonuclar]
        assert kaynaklar.count("dilekce_su.txt") == 1

    def test_bos_defter_bos_liste(self, tmp_path):
        """Boş defterde arama istisnasız boş liste döndürmeli."""
        defter = KayitDefteri(tmp_path / "bos.db")
        assert emsal_ara(SORGU_SU, kayit_defteri=defter) == []

    def test_bos_ve_anlamsiz_sorgu(self, tmp_path):
        """Boş/duraklardan ibaret sorgu boş liste döndürmeli."""
        defter = _dolu_defter(tmp_path)
        assert emsal_ara("", kayit_defteri=defter) == []
        assert emsal_ara("   ", kayit_defteri=defter) == []

    def test_limit_uygulanir(self, tmp_path):
        """limit sonuç sayısını sınırlamalı; bozuk limit varsayılana dönmeli."""
        defter = KayitDefteri(tmp_path / "limit.db")
        for i in range(5):
            defter.kaydet(
                _sonuc(f"dilekce_su_{i}.txt"),
                metin=DILEKCE_SU + f" Başvuru sıra numarası {i}.",
            )
        assert len(emsal_ara(SORGU_SU, limit=2, kayit_defteri=defter)) == 2
        assert len(emsal_ara(SORGU_SU, limit=50, kayit_defteri=defter)) == 5
        assert len(emsal_ara(SORGU_SU, limit="bozuk", kayit_defteri=defter)) == 3  # type: ignore[arg-type]

    def test_dizin_yeni_kaydi_gorur(self, tmp_path):
        """Kayıt sayısı değişince dizin tazelenmeli (sürüm damgası)."""
        defter = KayitDefteri(tmp_path / "tazele.db")
        defter.kaydet(_sonuc("rapor_sunucu.txt", "rapor"), metin=RAPOR_SUNUCU)
        arama = EmsalArama(defter)
        assert arama.ara(SORGU_SU) == []  # su dilekçesi henüz defterde yok
        defter.kaydet(_sonuc("dilekce_su.txt"), metin=DILEKCE_SU)
        sonuclar = arama.ara(SORGU_SU)  # aynı örnek, dizin yeniden kurulmalı
        assert sonuclar and sonuclar[0]["kaynak"] == "dilekce_su.txt"

    def test_asgari_benzerlik_alti_elenir(self, tmp_path):
        """Sonuçlar hiçbir zaman asgari benzerlik eşiğinin altına inmemeli."""
        defter = _dolu_defter(tmp_path)
        sonuclar = emsal_ara(SORGU_SU, limit=10, kayit_defteri=defter)
        assert all(s["benzerlik"] >= ASGARI_BENZERLIK for s in sonuclar)


class TestSemaGecisi:
    """Eski şemalı veritabanının yeni sürümle açılması (migration)."""

    def test_eski_semaya_sutunlar_eklenir(self, tmp_path):
        """Eski db açılınca metin_ozu/yazi_turu sütunları eklenmeli."""
        yol = tmp_path / "eski.db"
        _eski_semali_db(yol)
        KayitDefteri(yol)  # açılış migration'ı tetikler
        baglanti = sqlite3.connect(str(yol))
        try:
            sutunlar = {
                satir[1] for satir in baglanti.execute("PRAGMA table_info(islemler)")
            }
        finally:
            baglanti.close()
        assert "metin_ozu" in sutunlar
        assert "yazi_turu" in sutunlar

    def test_eski_kayit_korunur_ve_emsal_icin_okunur(self, tmp_path):
        """Eski kayıt veri kaybı olmadan emsal görünümünde okunabilmeli."""
        yol = tmp_path / "eski.db"
        _eski_semali_db(yol)
        defter = KayitDefteri(yol)
        kayitlar = defter.tum_kayitlar_emsal_icin()
        assert len(kayitlar) == 1
        assert kayitlar[0]["kaynak"] == "eski_dilekce.txt"
        assert kayitlar[0]["metin_ozu"] == ""  # NULL → boş metne indirgenir
        assert kayitlar[0]["yazi_turu"] == ""
        assert kayitlar[0]["ozet_ilk_200"].startswith("Su kesintisi")

    def test_gecis_sonrasi_kayit_ve_emsal_akisi(self, tmp_path):
        """Geçiş yapılan defterde yeni kayıt + emsal arama uçtan uca çalışmalı."""
        yol = tmp_path / "eski.db"
        _eski_semali_db(yol)
        defter = KayitDefteri(yol)
        defter.kaydet(_sonuc("dilekce_su.txt"), metin=DILEKCE_SU)
        sonuclar = emsal_ara(SORGU_SU, kayit_defteri=defter)
        assert sonuclar
        # Metin özlü yeni kayıt en üstte; özeti su kesintisinden söz eden
        # eski kayıt da (yalnız özetiyle) aday havuzundadır
        assert sonuclar[0]["kaynak"] == "dilekce_su.txt"

    def test_gecis_tekrar_acilista_tekrarlanmaz(self, tmp_path):
        """Aynı db'nin ikinci kez açılması hata/yinelenme üretmemeli."""
        yol = tmp_path / "eski.db"
        _eski_semali_db(yol)
        KayitDefteri(yol)
        defter = KayitDefteri(yol)  # ikinci açılış: sütunlar zaten var
        assert defter.istatistik()["toplam"] == 1
