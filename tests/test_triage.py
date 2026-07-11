"""
Triage (Akıllı Önceliklendirme) Agent testleri.

Tarih hesapları deterministik olsun diye agent'a sabit bir "bugün"
enjekte edilir (TriageAgent(bugun=...)). Takvim gerçekleri:
2026-06-22 Pazartesi, 2026-07-01 Çarşamba, 2026-07-06 Pazartesi.
"""

import sys
from datetime import date
from pathlib import Path

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import AgentState
from src.agents.triage_agent import TriageAgent, is_gunu_ekle


def _state(text, tur="diger", evrak_tarihi="", tarihler=None):
    """Testler için asgari dolulukta AgentState kurar."""
    state = AgentState(raw_text=text)
    state.classification = {"tur": tur, "tur_adi": tur, "guven": 0.9}
    state.extracted_info = {
        "evrak_tarihi": evrak_tarihi,
        "tarihler": tarihler or ([evrak_tarihi] if evrak_tarihi else []),
    }
    state.legislation_matches = []
    return state


class TestTriageAgent:
    """Triage Agent birim testleri."""

    def setup_method(self):
        """Her test öncesi sabit 'bugün' ile agent kur."""
        self.agent = TriageAgent(bugun=date(2026, 7, 1))

    # ------------------------------------------------------------------
    # Katman 1: aciliyet damgaları
    # ------------------------------------------------------------------

    def test_ivedi_damgasi(self):
        """İVEDİ damgalı yazı doğrudan 'ivedi' öncelik almalı."""
        state = _state(
            "T.C.\nAKÇOVA VALİLİĞİ\n\nİVEDİ\n\n"
            "Sayı : E-123\nKonu : Personel görevlendirmesi\n"
            "Gereğini rica ederim."
        )
        result = self.agent.run(state)
        assert result.triage["oncelik"] == "ivedi"
        tipler = [s["tip"] for s in result.triage["sinyaller"]]
        assert "aciliyet_damgasi" in tipler

    def test_cok_ivedi_tek_sinyal(self):
        """ÇOK İVEDİ damgası azami skor üretmeli, yalın İVEDİ ile çift sinyal olmamalı."""
        state = _state("ÇOK İVEDİ\n\nDeprem bölgesine sevkiyat hakkında yazıdır.")
        result = self.agent.run(state)
        assert result.triage["oncelik"] == "ivedi"
        assert result.triage["skor"] == 1.0
        damgalar = [
            s["deger"] for s in result.triage["sinyaller"]
            if s["tip"] == "aciliyet_damgasi"
        ]
        assert damgalar == ["ÇOK İVEDİ"]

    def test_gunludur_damgasi_yuksek(self):
        """GÜNLÜDÜR ibaresi (süreli evrak) en az 'yuksek' öncelik almalı."""
        state = _state("GÜNLÜDÜR\n\nSayı : E-42\nKonu : Veri girişi hakkında.")
        result = self.agent.run(state)
        assert result.triage["oncelik"] in ("yuksek", "ivedi")

    # ------------------------------------------------------------------
    # Katman 2: metin içi süre / açık son tarih
    # ------------------------------------------------------------------

    def test_15_gun_icinde_hesabi(self):
        """'15 gün içinde' evrak tarihine 15 takvim günü eklemeli."""
        state = _state(
            "Söz konusu eksikliklerin 15 gün içinde giderilmesi gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-16"
        assert result.triage["kalan_gun"] == 15
        assert result.triage["oncelik"] == "yuksek"

    def test_is_gunu_hesabi_hafta_sonu_atlar(self):
        """'5 iş günü içinde' hafta sonlarını atlamalı (Pzt 06.07 + 5 iş günü = Pzt 13.07)."""
        state = _state(
            "Raporun 5 iş günü içinde gönderilmesi rica olunur.",
            evrak_tarihi="06.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-13"

    def test_en_gec_acik_tarih(self):
        """'en geç <tarih>' kalıbı evrak tarihi olmasa da son tarih üretmeli."""
        state = _state(
            "Başvuruların en geç 15/08/2026 tarihine kadar iletilmesi gerekmektedir."
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-08-15"
        tipler = [s["tip"] for s in result.triage["sinyaller"]]
        assert "acik_son_tarih" in tipler

    def test_yaziyla_sure(self):
        """Yazıyla verilen süre ('on beş gün içinde') sayıya çevrilmeli."""
        state = _state(
            "Talebin on beş gün içinde sonuçlandırılması gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-16"

    def test_tarihsiz_evrakta_son_tarih_null(self):
        """Evrak tarihi yoksa göreli süre hesaplanamaz: son_tarih null + not."""
        state = _state("Eksikliklerin 30 gün içinde tamamlanması gerekmektedir.")
        result = self.agent.run(state)
        assert result.triage["son_tarih"] is None
        assert result.triage["kalan_gun"] is None
        assert result.triage["not"]

    # ------------------------------------------------------------------
    # Katman 3: yasal süre tablosu
    # ------------------------------------------------------------------

    def test_bilgi_edinme_15_is_gunu(self):
        """Bilgi edinme içeriği 4982 s. Kanun'a göre 15 iş günü süre almalı."""
        state = _state(
            "4982 sayılı Kanun kapsamında bilgi edinme başvurumun "
            "değerlendirilmesini arz ederim.",
            tur="dilekce",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        yasal = result.triage["yasal_sure"]
        assert yasal is not None
        assert yasal["sure_gun"] == 15
        assert yasal["tip"] == "is_gunu"
        assert "4982" in yasal["kaynak"]
        # Çrş 01.07.2026 + 15 iş günü = Çrş 22.07.2026
        assert result.triage["son_tarih"] == "2026-07-22"

    def test_dilekce_30_gun(self):
        """Dilekçe türü 3071 s. Kanun'a göre 30 takvim günü süre almalı."""
        state = _state(
            "Evimin önündeki yol çalışması hakkında gereğini arz ederim.",
            tur="dilekce",
            evrak_tarihi="22.06.2026",
        )
        result = self.agent.run(state)
        yasal = result.triage["yasal_sure"]
        assert yasal is not None
        assert yasal["sure_gun"] == 30
        assert yasal["tip"] == "takvim"
        assert "3071" in yasal["kaynak"]
        assert result.triage["son_tarih"] == "2026-07-22"

    # ------------------------------------------------------------------
    # Öncelik / kalan gün davranışı
    # ------------------------------------------------------------------

    def test_normal_evrak(self):
        """Aciliyet ve süre sinyali olmayan evrak 'normal' kalmalı."""
        state = _state(
            "Kurumumuz hizmet binasında yapılan boya çalışması "
            "tamamlanmış olup bilgilerinize sunulur.",
            tur="bilgilendirme",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["oncelik"] == "normal"
        assert result.triage["son_tarih"] is None
        assert result.triage["yasal_sure"] is None

    def test_gecmis_son_tarihte_kalan_gun_negatif(self):
        """Son tarihi geçmiş evrakta kalan_gun negatif olmalı ve öncelik ivediye çıkmalı."""
        agent = TriageAgent(bugun=date(2026, 8, 1))
        state = _state(
            "Cevabın en geç 20/07/2026 tarihine kadar verilmesi gerekmektedir."
        )
        result = agent.run(state)
        assert result.triage["kalan_gun"] == -12
        assert result.triage["oncelik"] == "ivedi"

    def test_yaklasan_sure_eskalasyonu(self):
        """Son tarihe 3 gün ve daha az kala öncelik ivediye yükselmeli."""
        agent = TriageAgent(bugun=date(2026, 7, 14))
        state = _state(
            "Eksikliklerin 15 gün içinde giderilmesi gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = agent.run(state)
        assert result.triage["kalan_gun"] == 2
        assert result.triage["oncelik"] == "ivedi"

    def test_en_erken_son_tarih_secilir(self):
        """Birden fazla süre kaydında en erken tarih bağlayıcı olmalı."""
        state = _state(
            "Taslağın 10 gün içinde, nihai raporun ise en geç "
            "15/08/2026 tarihine kadar gönderilmesi gerekmektedir.",
            evrak_tarihi="01.07.2026",
        )
        result = self.agent.run(state)
        assert result.triage["son_tarih"] == "2026-07-11"


class TestYardimcilar:
    """Yardımcı fonksiyon testleri."""

    def test_is_gunu_ekle_hafta_sonu(self):
        """Cuma + 1 iş günü = Pazartesi (2026-07-03 Cuma)."""
        assert is_gunu_ekle(date(2026, 7, 3), 1) == date(2026, 7, 6)

    def test_is_gunu_ekle_uzun(self):
        """Çarşamba 01.07 + 15 iş günü = Çarşamba 22.07."""
        assert is_gunu_ekle(date(2026, 7, 1), 15) == date(2026, 7, 22)
