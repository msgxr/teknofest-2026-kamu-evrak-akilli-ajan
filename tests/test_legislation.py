"""
Mevzuat Eşleştirme Agent birim testleri.

Madde referansı çıkarımı, madde-bazlı chunk üstverisi, hibrit arama
şeması (doc_id / mevzuat_adi / madde_no / gerekce / benzerlik), usul
mevzuatı garantisi, düzeltici (corrective) sorgu genişletme döngüsü ve
opsiyonel semantik katmanın zarif düşüşü test edilir.

Şartname Referansı (Görev 1):
    "İlgili mevzuat, yönetmelik veya standart yazışma kurallarını önerebilme"
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.legislation_agent import (
    DUZELTME_ESIGI,
    LegislationAgent,
    madde_etiketi,
    madde_referanslari,
)
from src.agents.orchestrator import AgentState
from src.utils.semantik_arama import (
    SemantikArama,
    YenidenSiralayici,
    puan_birlestir,
    rrf_birlestir,
)

# Testlerde kullanılan örnek dilekçe metni (kurgu; zengin mevzuat dağarcığı)
DILEKCE_METNI = """
KONAKLI BELEDİYE BAŞKANLIĞINA

Konu : Park alanındaki gürültü sorunu hakkında

Mahallemizdeki parkta akşam saatlerinde yüksek sesle müzik çalınmakta,
gürültü nedeniyle huzurumuz kaçmaktadır. Zabıta ekiplerince gerekli
denetimin yapılmasını ve sonucun tarafıma bildirilmesini arz ederim.

Tarih : 01/07/2026
Ad Soyad : Kurgu Kişi
Adres : Kurgu Mah. Deneme Sok. No:1
İmza : (imzalıdır)
"""

# Mevzuat korpusu söz dağarcığıyla HİÇ örtüşmeyen uydurma metin
# (düzeltici döngünün tetiklenme senaryosu)
UYDURMA_METIN = "zzyx qwrtp flumzo brixtel vandaqu plemzor krastivo"


def _dilekce_state(metin: str = DILEKCE_METNI, konu: str = "") -> AgentState:
    """Sınıflandırması hazır bir dilekçe durumu (state) kurar.

    konu boş bırakılırsa sorgu yalnızca ham metinden kurulur — düzeltici
    döngü testleri için korpus dışı metnin 'temiz' kalması gerekir.
    """
    state = AgentState(raw_text=metin)
    state.classification = {"tur": "dilekce", "guven": 0.9}
    state.extracted_info = {"konu": konu}
    return state


class TestMaddeReferanslari:
    """madde_referanslari / madde_etiketi birim testleri."""

    def test_tek_madde(self):
        """Parantezli tek madde atfı yakalanmalı."""
        assert madde_referanslari("gerekli denetim yapılır (m. 14).") == ["14"]

    def test_aralik(self):
        """Tire ile verilen madde aralığı tek girdi olarak yakalanmalı."""
        assert madde_referanslari("usuller sayılmıştır (m. 22-23).") == ["22-23"]

    def test_kesme_ekli_parantezsiz(self):
        """Korpustaki 'm. 4'te' biçimi (parantezsiz, kesme ekli) yakalanmalı."""
        assert madde_referanslari("m. 4'te öngörülen şartlar") == ["4"]

    def test_coklu_ve_tekrarsiz(self):
        """Birden çok atıf sıra korunarak ve tekrarsız dönmeli."""
        metin = "önce (m. 5), sonra (m. 3) ve yine (m. 5) düzenler."
        assert madde_referanslari(metin) == ["5", "3"]

    def test_kanun_numarasi_yakalanmamali(self):
        """'3071 sayılı Kanun' bir madde atfı DEĞİLDİR."""
        assert madde_referanslari("3071 sayılı Dilekçe Hakkı Kanunu uyarınca") == []

    def test_madde_kelimesi_yakalanmamali(self):
        """Numarasız 'madde/maddedir' sözcüğü atıf sayılmamalı."""
        assert madde_referanslari("belediyenin görevlerini düzenleyen bu maddedir") == []

    def test_bos_metin(self):
        """Boş metinde boş liste dönmeli (bilgi notları için normal akış)."""
        assert madde_referanslari("") == []

    def test_madde_etiketi(self):
        """Etiket insan-okur biçimde birleşmeli."""
        assert madde_etiketi(["4", "22-23"]) == "m. 4, m. 22-23"
        assert madde_etiketi([]) == ""


class TestKorpusChunklari:
    """Korpus yükleme ve madde-bazlı chunk üstverisi testleri."""

    def setup_method(self):
        self.agent = LegislationAgent()
        self.agent._ensure_index()

    def test_korpus_yuklendi(self):
        """15 mevzuat dosyası bölümlere ayrılarak yüklenmeli."""
        chunks = LegislationAgent._chunks
        assert chunks, "Mevzuat korpusu boş olmamalı"
        assert len({c["doc_id"] for c in chunks}) >= 15

    def test_her_chunk_madde_alani_tasir(self):
        """Her chunk'ta madde_no listesi bulunmalı (boş olabilir)."""
        for chunk in LegislationAgent._chunks or []:
            assert isinstance(chunk.get("madde_no"), list)

    def test_3071_zorunlu_bilgiler_maddesi(self):
        """3071 'Zorunlu Bilgiler' bölümü m. 4 atfı taşımalı."""
        chunk = next(
            c for c in (LegislationAgent._chunks or [])
            if c["doc_id"] == "dilekce_hakki_kanunu_3071"
            and "Zorunlu Bilgiler" in c["bolum"]
        )
        assert "4" in chunk["madde_no"]


class TestHibritArama:
    """Hibrit arama şeması ve usul mevzuatı garantisi testleri."""

    def setup_method(self):
        self.agent = LegislationAgent()

    def test_oneri_semasi(self):
        """Her öneri P0-1 şemasını taşımalı: mevzuat adı + madde + gerekçe + skor."""
        state = self.agent.run(_dilekce_state())
        assert state.legislation_matches, "Dilekçe için öneri üretilmeli"
        for m in state.legislation_matches:
            for anahtar in ("doc_id", "mevzuat_adi", "madde_no", "madde_etiketi",
                            "gerekce", "benzerlik", "baslik", "icerik_ozeti", "kaynak"):
                assert anahtar in m, f"Öneri '{anahtar}' alanını taşımalı"
            assert m["gerekce"], "Gerekçe boş olmamalı"

    def test_usul_mevzuati_basta(self):
        """Dilekçede ilk öneri 3071 olmalı ve benzerliği >= 0.8 raporlanmalı."""
        state = self.agent.run(_dilekce_state())
        ilk = state.legislation_matches[0]
        assert ilk["doc_id"] == "dilekce_hakki_kanunu_3071"
        assert ilk["benzerlik"] >= 0.8
        assert "usul mevzuatı" in ilk["gerekce"]

    def test_arama_meta_yazilir(self):
        """Arama yöntemi ve düzeltme döngüsü kaydı state meta'sına yazılmalı."""
        state = self.agent.run(_dilekce_state())
        meta = state.legislation_meta
        assert meta.get("yontem") == "bm25"  # çekirdek ortamda opsiyonel katman yok
        assert "duzeltme_dongusu" in meta
        assert meta["duzeltme_dongusu"]["esik"] == DUZELTME_ESIGI

    def test_zengin_metinde_dongu_tetiklenmez(self):
        """Mevzuat dağarcığıyla örtüşen metinde düzeltici döngü gereksizdir."""
        state = self.agent.run(_dilekce_state())
        assert state.legislation_meta["duzeltme_dongusu"]["uygulandi"] is False

    def test_kural_tabanli_son_care_semasi(self):
        """Kural tabanlı son çare de aynı şemayı (doc_id + gerekce) üretmeli."""
        matches = self.agent._rule_based_match("dilekce")
        assert matches
        for m in matches:
            assert m["doc_id"]
            assert m["gerekce"]
            assert isinstance(m["madde_no"], list)


class TestDuzelticiDongu:
    """Düzeltici (corrective) sorgu genişletme döngüsü testleri."""

    def setup_method(self):
        self.agent = LegislationAgent()

    def test_dusuk_skorda_dongu_uygulanir(self):
        """Korpus dışı söz dağarcığında tür genişletmesi devreye girmeli."""
        state = self.agent.run(_dilekce_state(UYDURMA_METIN))
        duzeltme = state.legislation_meta["duzeltme_dongusu"]
        assert duzeltme["uygulandi"] is True
        assert duzeltme["eklenen_terimler"], "Genişletme terimleri kaydedilmeli"
        assert state.legislation_matches, "Döngü sonrası öneri üretilmeli"

    def test_dongu_gerekceye_islenir(self):
        """Döngüyle bulunan önerilerin gerekçesinde düzeltme izi olmalı."""
        state = self.agent.run(_dilekce_state(UYDURMA_METIN))
        gerekceler = " | ".join(
            m.get("gerekce", "") for m in state.legislation_matches
        )
        assert "düzeltici döngü" in gerekceler or "usul mevzuatı" in gerekceler

    def test_turu_bilinmeyen_evrakta_dongu_yok(self):
        """Genişletme sözlüğünde olmayan türde döngü denenmemeli."""
        state = AgentState(raw_text=UYDURMA_METIN)
        state.classification = {"tur": "diger", "guven": 0.5}
        state = self.agent.run(state)
        assert state.legislation_meta["duzeltme_dongusu"]["uygulandi"] is False


class TestPuanBirlestir:
    """Hibrit puan birleşimi (saf Python) birim testleri."""

    def test_dense_bos_ise_bm25_doner(self):
        """Semantik taraf boşken BM25 puanları aynen korunmalı."""
        bm25 = {1: 1.0, 2: 0.5}
        assert puan_birlestir(bm25, {}) == bm25

    def test_bm25_bos_ise_dense_doner(self):
        """BM25 tarafı boşken semantik puanlar aynen korunmalı."""
        dense = {3: 0.9}
        assert puan_birlestir({}, dense) == dense

    def test_disbukey_birlesim(self):
        """0.6/0.4 ağırlıkla birleşim; tek taraflı indeksler 0 sayılmalı."""
        bm25 = {1: 1.0, 2: 0.5}
        dense = {2: 1.0, 3: 0.8}
        sonuc = puan_birlestir(bm25, dense, bm25_agirlik=0.6)
        assert sonuc[1] == pytest.approx(0.6)
        assert sonuc[2] == pytest.approx(0.5 * 0.6 + 1.0 * 0.4)
        assert sonuc[3] == pytest.approx(0.8 * 0.4)


class TestRRF:
    """rrf_birlestir (Reciprocal Rank Fusion) birim testleri."""

    def test_iki_listede_ust_sirada_olan_kazanir(self):
        r = rrf_birlestir([{1: 0.9, 2: 0.5, 3: 0.1}, {1: 0.8, 3: 0.7, 2: 0.2}])
        sirali = sorted(r, key=r.get, reverse=True)
        assert sirali[0] == 1

    def test_tek_liste_sirayi_korur(self):
        # Tek liste → RRF o listenin sırasını korur (offline çekirdek davranışı)
        r = rrf_birlestir([{5: 0.9, 6: 0.3, 7: 0.6}])
        assert sorted(r, key=r.get, reverse=True) == [5, 7, 6]

    def test_bos_liste(self):
        assert rrf_birlestir([]) == {}
        assert rrf_birlestir([{}, {}]) == {}

    def test_k_yumusatma(self):
        # Küçük k sıra farklarını büyütür
        r_kucuk = rrf_birlestir([{1: 0.9, 2: 0.1}], k=1)
        r_buyuk = rrf_birlestir([{1: 0.9, 2: 0.1}], k=1000)
        assert (r_kucuk[1] - r_kucuk[2]) > (r_buyuk[1] - r_buyuk[2])


class TestOpsiyonelKatmanZarifDusus:
    """Opsiyonel semantik/rerank katmanların varsayılan kapalılığı testleri."""

    def test_semantik_varsayilan_kapali(self):
        """EMBEDDING_SEMANTIK_AKTIF verilmedikçe katman devre dışı olmalı."""
        assert SemantikArama().aktif() is False

    def test_rerank_varsayilan_kapali(self):
        """EMBEDDING_RERANK_AKTIF verilmedikçe rerank devre dışı olmalı."""
        assert YenidenSiralayici().aktif() is False

    def test_kapali_katman_arama_bos_doner(self):
        """Kapalı katmanda indeksleme/arama sessizce boş dönmeli (çökme yok)."""
        sa = SemantikArama()
        assert sa.indeksle(["örnek bölüm metni"]) is False
        assert sa.ara("örnek sorgu") == []
