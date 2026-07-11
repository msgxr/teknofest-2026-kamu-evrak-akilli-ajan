"""
Taslak Kalite Hakemi birim testleri (P1-6).

Kural tabanlı hakemin 0-100 ölçeği, üslup cezaları, mevzuat temellilik
(RAGAS-vari groundedness) ve halüsinasyon-atıf tespiti; LLM yokken
kural yoluna düşüş.

Şartname Referansı (Görev 2): yazı şablonu/taslak kalitesi kanıtı.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.taslak_hakemi import (
    TEMELLILIK_GENEL_ATIF,
    TEMELLILIK_UYDURMA_ATIF,
    taslak_puanla,
)

TEMIZ_TASLAK = """T.C.
AKÇOVA VALİLİĞİ
Yazı İşleri Müdürlüğü

Sayı   : (TASLAK — sayı EBYS tarafından verilecektir)      12.07.2026
Konu   : Park aydınlatması hakkında

KURGU BAKANLIĞINA

İlgi   : 01.07.2026 tarihli yazı.

İlgi yazı incelenmiştir.
Söz konusu başvuru, 3071 Sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun hükümleri kapsamında değerlendirilmiştir.

Bilgilerinize arz ederim.

                                                        (e-imzalıdır)
                                                        Müdür
"""

MATCHES = [
    {
        "doc_id": "dilekce_hakki_kanunu_3071",
        "baslik": "3071 Sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun",
        "benzerlik": 0.85,
    },
]

FORMAT_TAM = {"skor": 1.0, "uygun": True}


class TestKuralHakem:
    """Kural tabanlı hakem yolu testleri (LLM'siz ortam)."""

    def test_temiz_taslak_yuksek_puan(self):
        """Biçimi tam, üslubu temiz, atıfı güçlü taslak >= 90 puan almalı."""
        sonuc = taslak_puanla(TEMIZ_TASLAK, FORMAT_TAM, MATCHES)
        assert sonuc["yontem"] == "kural_hakem"  # CI ortamında LLM yok
        assert sonuc["puan"] >= 90
        assert sonuc["bilesenler"]["bicim"] == 100
        assert sonuc["bilesenler"]["mevzuat_temellilik"] == 100

    def test_puan_sinirlari(self):
        """Puan ve bileşenler her koşulda [0, 100] aralığında kalmalı."""
        sonuc = taslak_puanla("", {}, [])
        assert 0 <= sonuc["puan"] <= 100
        for deger in sonuc["bilesenler"].values():
            assert 0 <= deger <= 100

    def test_birinci_sahis_uslup_cezasi(self):
        """Birinci şahıs anlatı üslup puanını düşürmeli."""
        kirli = TEMIZ_TASLAK.replace(
            "İlgi yazı incelenmiştir.",
            "Ben bu durumdan mağdur olmaktayım. "
            "Benim talebimin karşılanmasını istiyorum.",
        )
        temiz = taslak_puanla(TEMIZ_TASLAK, FORMAT_TAM, MATCHES)
        sonuc = taslak_puanla(kirli, FORMAT_TAM, MATCHES)
        assert sonuc["bilesenler"]["uslup"] < temiz["bilesenler"]["uslup"]
        assert any("birinci şahıs" in n for n in sonuc["notlar"])

    def test_yabanci_kelime_cezasi(self):
        """Yabancı kelime kullanımı üslup puanını düşürmeli."""
        kirli = TEMIZ_TASLAK.replace(
            "İlgi yazı incelenmiştir.",
            "İlgi mail incelenmiş olup feedback verilecektir.",
        )
        sonuc = taslak_puanla(kirli, FORMAT_TAM, MATCHES)
        assert sonuc["bilesenler"]["uslup"] <= 80
        assert any("yabancı kelime" in n for n in sonuc["notlar"])

    def test_kapanissiz_taslak_cezasi(self):
        """Kapanış ifadesi olmayan taslak üslup cezası almalı."""
        kapanissiz = TEMIZ_TASLAK.replace("Bilgilerinize arz ederim.", "")
        sonuc = taslak_puanla(kapanissiz, FORMAT_TAM, MATCHES)
        assert any("kapanış" in n for n in sonuc["notlar"])


class TestMevzuatTemellilik:
    """RAGAS-vari mevzuat temellilik (groundedness) testleri."""

    def test_uydurma_atif_agir_ceza(self):
        """Öneri listesinde olmayan atıf halüsinasyon sayılıp cezalandırılmalı."""
        uydurma = TEMIZ_TASLAK.replace(
            "3071 Sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun",
            "9999 sayılı Kurgu İşleri Kanunu",
        )
        sonuc = taslak_puanla(uydurma, FORMAT_TAM, MATCHES)
        assert sonuc["bilesenler"]["mevzuat_temellilik"] == TEMELLILIK_UYDURMA_ATIF
        assert any("halüsinasyon" in n for n in sonuc["notlar"])

    def test_genel_atif_notr_puan(self):
        """Özgül atıf yoksa (genel ifade) nötr-dürüst puan verilmeli."""
        genel = TEMIZ_TASLAK.replace(
            "3071 Sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun hükümleri",
            "ilgili mevzuat hükümleri",
        )
        sonuc = taslak_puanla(genel, FORMAT_TAM, MATCHES)
        assert sonuc["bilesenler"]["mevzuat_temellilik"] == TEMELLILIK_GENEL_ATIF

    def test_zayif_eslesmeli_atif_dusuk_puan(self):
        """Zayıf-eşleşme işaretli öneriye dayanan atıf düşük puan almalı."""
        zayif_matches = [dict(MATCHES[0], zayif_esleme=True, benzerlik=0.2)]
        sonuc = taslak_puanla(TEMIZ_TASLAK, FORMAT_TAM, zayif_matches)
        assert sonuc["bilesenler"]["mevzuat_temellilik"] <= 40

    def test_dusuk_benzerlikli_atif_orantili(self):
        """Atıf puanı mutlak benzerlikle orantılı olmalı (0.3/0.6 → 50)."""
        orta = [dict(MATCHES[0], benzerlik=0.3)]
        sonuc = taslak_puanla(TEMIZ_TASLAK, FORMAT_TAM, orta)
        assert sonuc["bilesenler"]["mevzuat_temellilik"] == 50


class TestPipelineEntegrasyonu:
    """Hakem sonucunun pipeline çıktısına yansıması."""

    def test_taslak_kalitesi_ciktida(self):
        """Uçtan uca sonuç sözlüğü taslak_kalitesi alanını taşımalı."""
        from src.agents.draft_writer_agent import DraftWriterAgent
        from src.agents.orchestrator import AgentState

        state = AgentState(raw_text=TEMIZ_TASLAK)
        state.classification = {"tur": "dilekce", "guven": 0.9}
        state.legislation_matches = list(MATCHES)
        state = DraftWriterAgent().run(state)
        assert state.draft_quality, "Hakem sonucu doldurulmalı"
        assert 0 <= state.draft_quality["puan"] <= 100
        assert state.draft_quality["yontem"] in ("kural_hakem", "llm_hakem")
