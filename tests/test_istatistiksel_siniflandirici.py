# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
İstatistiksel Sınıflandırıcı (saf Python Multinomial NB) testleri.

Kapsam: eğitim, tahmin, JSON serileştirme/önbellekli yükleme, boş metin
davranışı ve ClassificationAgent hibrit ensemble entegrasyonu.
"""

import json
import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.istatistiksel_siniflandirici import (
    IstatistikselSiniflandirici,
    egit,
    model_kaydet,
    ozellik_cikar,
    tahmin,
)

# Küçük sentetik eğitim korpusu: türe özgü sözcük dağılımları belirgin,
# gerçek resmî yazışma diline uygun kalıplar.
EGITIM_KORPUSU = [
    ("Toplantı tutanağıdır. Katılımcılar gündemi görüştü, tutanak imza altına alındı.", "tutanak"),
    ("İnceleme tutanağı: hazır bulunanlar tespitleri tutanakla kayıt altına aldı.", "tutanak"),
    ("Müdürlüğüne, mağduriyetimin giderilmesini talep ediyorum. Gereğini arz ederim.", "dilekce"),
    ("Başkanlığına, başvurumun değerlendirilmesini istirham ederim. Saygılarımla arz ederim.", "dilekce"),
    ("İlgide kayıtlı yazınıza cevaben görüşümüz ekte bilgilerinize sunulmuştur.", "cevap_yazisi"),
    ("Dilekçenize istinaden yapılan inceleme sonucunda talebiniz uygun bulunmuştur.", "cevap_yazisi"),
]


class TestEgitim:
    """egit() birim testleri."""

    def test_model_alanlari(self):
        """Eğitilen model gerekli alanları içermeli."""
        model = egit(EGITIM_KORPUSU)
        for alan in (
            "surum", "yontem", "alpha", "belge_sayisi", "sinif_belge_sayilari",
            "sozluk_boyutu", "log_oncul", "idf", "log_olasilik",
            "bilinmeyen_log_olasilik",
        ):
            assert alan in model, f"'{alan}' alanı eksik"

        assert model["belge_sayisi"] == len(EGITIM_KORPUSU)
        assert model["sinif_belge_sayilari"] == {
            "tutanak": 2, "dilekce": 2, "cevap_yazisi": 2,
        }
        assert model["sozluk_boyutu"] > 0

    def test_log_olasiliklar_negatif(self):
        """Log-olasılıklar ve öncüller log-uzayda (<= 0) olmalı."""
        model = egit(EGITIM_KORPUSU)
        for oncul in model["log_oncul"].values():
            assert oncul <= 0
        for sinif_olasiliklari in model["log_olasilik"].values():
            for deger in sinif_olasiliklari.values():
                assert deger < 0
        # Laplace: sınıfta gözlenmeyen terim, gözlenenden daha az olası
        for sinif, bilinmeyen in model["bilinmeyen_log_olasilik"].items():
            for deger in model["log_olasilik"][sinif].values():
                assert bilinmeyen <= deger

    def test_bos_egitim_verisi_hata(self):
        """Boş eğitim listesi ValueError vermeli."""
        with pytest.raises(ValueError):
            egit([])

    def test_gecersiz_alpha_hata(self):
        """alpha <= 0 ValueError vermeli (Laplace düzeltmesi pozitif olmalı)."""
        with pytest.raises(ValueError):
            egit(EGITIM_KORPUSU, alpha=0.0)


class TestTahmin:
    """tahmin() birim testleri."""

    def setup_method(self):
        self.model = egit(EGITIM_KORPUSU)

    def test_egitim_orneklerini_dogru_tahmin(self):
        """Eğitim örneklerinin sınıfı doğru tahmin edilmeli."""
        for metin, beklenen in EGITIM_KORPUSU:
            tur, _ = tahmin(self.model, metin)
            assert tur == beklenen, f"{beklenen!r} bekleniyordu, {tur!r} döndü"

    def test_gorulmemis_metin(self):
        """Aynı türde görülmemiş metin doğru sınıflanmalı."""
        tur, olasiliklar = tahmin(
            self.model,
            "İş bu tutanak toplantı sonunda hazır bulunanlarca imza altına alınmıştır.",
        )
        assert tur == "tutanak"
        assert olasiliklar["tutanak"] == max(olasiliklar.values())

    def test_olasiliklar_dagilim(self):
        """Olasılıklar [0,1] aralığında olmalı ve 1'e toplanmalı."""
        _, olasiliklar = tahmin(self.model, "Talebimin değerlendirilmesini arz ederim.")
        assert set(olasiliklar) == {"tutanak", "dilekce", "cevap_yazisi"}
        assert all(0.0 <= p <= 1.0 for p in olasiliklar.values())
        assert sum(olasiliklar.values()) == pytest.approx(1.0)

    def test_bos_metin(self):
        """Boş metinde sonsal dağılım öncüle eşit olmalı (çökmemeli)."""
        tur, olasiliklar = tahmin(self.model, "")
        assert tur in {"tutanak", "dilekce", "cevap_yazisi"}
        assert sum(olasiliklar.values()) == pytest.approx(1.0)
        # Kanıt yok -> sonsal = öncül (sınıf başına 2/6)
        for p in olasiliklar.values():
            assert p == pytest.approx(1.0 / 3.0, abs=1e-6)

    def test_sozluk_disi_metin(self):
        """Tamamen sözlük dışı metin öncül dağılımıyla dönmeli."""
        _, olasiliklar = tahmin(self.model, "xylophone quantum zzz qqq www")
        assert sum(olasiliklar.values()) == pytest.approx(1.0)

    def test_gecersiz_model_hata(self):
        """log_oncul alanı olmayan model ValueError vermeli."""
        with pytest.raises(ValueError):
            tahmin({}, "herhangi bir metin")


class TestOzellikCikar:
    """ozellik_cikar() birim testleri."""

    def test_kelime_ve_ngram_birlikte(self):
        """Hem kelime token'ları hem karakter 3-gram'ları üretilmeli."""
        ozellikler = ozellik_cikar("Tutanak imza")
        assert "tutanak" in ozellikler
        assert "imza" in ozellikler
        # Kelime sınırı işaretli 3-gram'lar (ör. '<tu', 'ak>')
        assert "c3:<tu" in ozellikler
        assert "c3:ak>" in ozellikler

    def test_bos_metin_bos_sozluk(self):
        """Boş/None metin boş öznitelik sözlüğü vermeli."""
        assert ozellik_cikar("") == {}
        assert ozellik_cikar(None) == {}


class TestSerilestirme:
    """JSON serileştirme ve önbellekli yükleme testleri."""

    def setup_method(self):
        IstatistikselSiniflandirici.onbellek_temizle()

    def teardown_method(self):
        IstatistikselSiniflandirici.onbellek_temizle()

    def test_json_gidis_donus(self, tmp_path):
        """Kaydet-yükle turu tahmin sonucunu değiştirmemeli."""
        model = egit(EGITIM_KORPUSU)
        yol = tmp_path / "model.json"
        model_kaydet(model, yol)

        yuklenen = IstatistikselSiniflandirici.yukle(yol)
        assert yuklenen is not None

        metin = "İlgide kayıtlı yazınıza cevaben bilgi verilmiştir."
        tur1, olasilik1 = tahmin(model, metin)
        tur2, olasilik2 = tahmin(yuklenen, metin)
        assert tur1 == tur2
        for sinif in olasilik1:
            assert olasilik1[sinif] == pytest.approx(olasilik2[sinif])

    def test_onbellek_ayni_nesneyi_dondurur(self, tmp_path):
        """Değişmemiş dosya ikinci yüklemede önbellekten gelmeli."""
        yol = tmp_path / "model.json"
        model_kaydet(egit(EGITIM_KORPUSU), yol)
        birinci = IstatistikselSiniflandirici.yukle(yol)
        ikinci = IstatistikselSiniflandirici.yukle(yol)
        assert birinci is ikinci

    def test_olmayan_dosya_none(self, tmp_path):
        """Var olmayan model dosyası None döndürmeli (zarif düşüş)."""
        assert IstatistikselSiniflandirici.yukle(tmp_path / "yok.json") is None

    def test_bozuk_json_none(self, tmp_path):
        """Bozuk JSON dosyası None döndürmeli."""
        yol = tmp_path / "bozuk.json"
        yol.write_text("{bozuk json", encoding="utf-8")
        assert IstatistikselSiniflandirici.yukle(yol) is None

    def test_eksik_semali_model_none(self, tmp_path):
        """Gerekli alanları taşımayan JSON None döndürmeli."""
        yol = tmp_path / "eksik.json"
        yol.write_text(json.dumps({"log_oncul": {}}), encoding="utf-8")
        assert IstatistikselSiniflandirici.yukle(yol) is None


class TestEnsembleEntegrasyonu:
    """ClassificationAgent hibrit ensemble entegrasyon testleri."""

    @pytest.fixture(autouse=True)
    def _offline_llm(self, monkeypatch):
        """LLM eskalasyonunu determinizm için devre dışı bırak."""
        import src.models.llm_wrapper as llm_wrapper

        monkeypatch.setenv("LLM_BACKEND", "offline")
        monkeypatch.setattr(llm_wrapper, "_default_llm", None)
        yield
        llm_wrapper._default_llm = None

    def _tutanak_metni(self):
        return (
            "TOPLANTI TUTANAĞI\n"
            "Toplantı tarihi: 08/07/2026\n"
            "Katılımcılar: birim amirleri\n"
            "Gündem maddeleri görüşülmüş, iş bu tutanak imza altına alınmıştır.\n"
        )

    def test_hibrit_ensemble_alanlari(self, monkeypatch):
        """Model varken sonuç hibrit_ensemble alanlarını taşımalı."""
        from src.agents.classification_agent import ClassificationAgent
        from src.agents.orchestrator import AgentState

        model = egit(EGITIM_KORPUSU)
        monkeypatch.setattr(
            IstatistikselSiniflandirici,
            "yukle",
            classmethod(lambda cls, yol=None: model),
        )

        agent = ClassificationAgent(method="llm")
        state = agent.run(AgentState(raw_text=self._tutanak_metni()))
        sonuc = state.classification

        assert sonuc["yontem"] == "hibrit_ensemble"
        assert sonuc["tur"] == "tutanak"
        for alan in ("kural_guven", "kural_tur", "ml_guven", "ml_tur", "ml_skorlar"):
            assert alan in sonuc, f"'{alan}' alanı eksik"
        assert 0.0 <= sonuc["guven"] <= 1.0

    def test_model_yoksa_kural_tabanli(self, monkeypatch):
        """Model dosyası yoksa saf kural tabanlı moda düşmeli."""
        from src.agents.classification_agent import ClassificationAgent
        from src.agents.orchestrator import AgentState

        monkeypatch.setattr(
            IstatistikselSiniflandirici,
            "yukle",
            classmethod(lambda cls, yol=None: None),
        )

        agent = ClassificationAgent(method="llm")
        state = agent.run(AgentState(raw_text=self._tutanak_metni()))
        assert state.classification["yontem"] == "kural_tabanli"
        assert state.classification["tur"] == "tutanak"

    def test_rule_based_modu_saf_kural(self):
        """'rule_based' modu ML kullanmamalı (arayüz korunur)."""
        from src.agents.classification_agent import ClassificationAgent
        from src.agents.orchestrator import AgentState

        agent = ClassificationAgent(method="rule_based")
        state = agent.run(AgentState(raw_text=self._tutanak_metni()))
        assert state.classification["yontem"] == "kural_tabanli"
        assert "ml_guven" not in state.classification
