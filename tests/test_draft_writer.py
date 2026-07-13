# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Taslak Yazma Agent — madde-referanslı format denetçisi birim testleri.

Denetim kurallarının {kural_id, kural, durum, detay, dayanak, agirlik}
şeması, ağırlıklı skor formülü, koşullu kuralların yalnızca bağlam
varken eklenmesi, bitiş ifadesi ↔ muhatap hiyerarşisi tutarlılığı,
gizlilik damgası kısıtlı modu ve yetki devri imza düzeni test edilir.

Şartname Referansı (Görev 2):
    "Yazının kamu kurumlarının resmî yazışma kurallarına uygunluğunun
     denetlenmesi"
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Proje kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.draft_writer_agent import (
    DraftWriterAgent,
    TASLAK_SAYI_IBARESI,
)
from src.agents.orchestrator import AgentState

# Denetimden tam geçmesi beklenen örnek taslak (üst kuruluşa arz)
ORNEK_TASLAK = f"""T.C.
AKÇOVA VALİLİĞİ
Yazı İşleri Müdürlüğü

Sayı   : {TASLAK_SAYI_IBARESI}                       11.07.2026
Konu   : Park aydınlatması hakkında

ÇEVRE, ŞEHİRCİLİK VE İKLİM DEĞİŞİKLİĞİ BAKANLIĞINA

İlgi   : 01.07.2026 tarihli yazı.

İlgi yazı incelenmiş olup gerekli değerlendirme yapılmıştır.

Bilgilerinize arz ederim.

                                                        (e-imzalıdır)
                                                        Müdür
"""


def _denetle(taslak: str, yazi_turu: str = "ust_yazi", gizlilik: str = "") -> dict:
    return DraftWriterAgent()._validate_format(
        taslak, yazi_turu, gizlilik_damgasi=gizlilik
    )


def _kural(sonuc: dict, kural_id: str):
    return next(
        (k for k in sonuc["kontroller"] if k["kural_id"] == kural_id), None
    )


class TestKuralSemasi:
    """Madde-referanslı kural şeması testleri."""

    def test_her_kural_tam_semayi_tasir(self):
        """Her kontrol {kural_id, kural, durum, detay, dayanak, agirlik} taşımalı."""
        sonuc = _denetle(ORNEK_TASLAK)
        assert sonuc["kontroller"], "Kontrol listesi boş olmamalı"
        for k in sonuc["kontroller"]:
            for anahtar in ("kural_id", "kural", "durum", "detay", "dayanak", "agirlik"):
                assert anahtar in k, f"'{anahtar}' alanı eksik: {k}"

    def test_dayanaklar_madde_referansli(self):
        """Yönetmelik kuralları 'Yön. (2646) m.X' biçiminde dayanak taşımalı."""
        sonuc = _denetle(ORNEK_TASLAK)
        yonetmelik_kurallari = [
            k for k in sonuc["kontroller"] if k["kural_id"] != "yer_tutucu"
        ]
        for k in yonetmelik_kurallari:
            assert "Yön. (2646) m." in k["dayanak"], (
                f"{k['kural_id']} kuralında madde dayanağı yok: {k['dayanak']}"
            )

    def test_yer_tutucu_ic_kalite_kurali(self):
        """Yer tutucu kuralı yönetmelik maddesi taşımaz (uydurma atıf yok)."""
        k = _kural(_denetle(ORNEK_TASLAK), "yer_tutucu")
        assert k is not None
        assert "iç kalite" in k["dayanak"]

    def test_eski_anahtarlar_korunur(self):
        """Geriye dönük uyumluluk: kural/durum/detay anahtarları yaşamalı."""
        sonuc = _denetle(ORNEK_TASLAK)
        k = sonuc["kontroller"][0]
        assert "kural" in k and "durum" in k and "detay" in k


class TestSkorFormulu:
    """Ağırlıklı skor ve 'uygun' hesabı testleri."""

    def test_tam_uyumlu_taslak(self):
        """Örnek taslak tüm kurallardan geçmeli (skor 1.0, uygun)."""
        sonuc = _denetle(ORNEK_TASLAK)
        basarisizlar = [k["kural_id"] for k in sonuc["kontroller"] if not k["durum"]]
        assert not basarisizlar, f"Başarısız kurallar: {basarisizlar}"
        assert sonuc["skor"] == 1.0
        assert sonuc["uygun"] is True

    def test_yer_tutucu_kalirsa_uygun_degil(self):
        """Skor yüksek olsa bile yer tutucu kalan taslak 'uygun' olamaz."""
        taslak = ORNEK_TASLAK + "\n[EKSİK ALAN]"
        sonuc = _denetle(taslak)
        assert sonuc["uygun"] is False

    def test_dusuk_agirlikli_kural_skoru_az_etkiler(self):
        """0.25 ağırlıklı yabancı kelime ihlali skoru 1.0 ağırlık kadar düşürmemeli."""
        yabanci = ORNEK_TASLAK.replace(
            "gerekli değerlendirme", "gerekli feedback değerlendirmesi"
        )
        sonuc = _denetle(yabanci)
        k = _kural(sonuc, "yabanci_kelime")
        assert k is not None and k["durum"] is False
        assert "feedback" in k["detay"]
        # 0.25/toplam kayıp; skor hâlâ 0.9 üzerinde kalmalı
        assert sonuc["skor"] >= 0.9


class TestSayiVeKonuKurallari:
    """m.11 sayı biçimi ve m.13/2 konu özlüğü testleri."""

    def test_taslak_sayi_ibaresi_kabul(self):
        """Dürüst EBYS ibaresi sayı biçimi kuralından geçmeli."""
        k = _kural(_denetle(ORNEK_TASLAK), "sayi_bicimi")
        assert k is not None and k["durum"] is True

    def test_yonetmelik_bicimli_sayi_kabul(self):
        """m.11/2 örnek biçimindeki gerçek sayı da geçmeli."""
        taslak = ORNEK_TASLAK.replace(
            TASLAK_SAYI_IBARESI, "E-67915368-903.07.02-4752"
        )
        k = _kural(_denetle(taslak), "sayi_bicimi")
        assert k is not None and k["durum"] is True

    def test_serbest_metin_sayi_uyari(self):
        """Biçimsiz (uydurma) sayı değeri kuraldan geçmemeli."""
        taslak = ORNEK_TASLAK.replace(TASLAK_SAYI_IBARESI, "2026/418")
        k = _kural(_denetle(taslak), "sayi_bicimi")
        assert k is not None and k["durum"] is False

    def test_uzun_konu_uyari(self):
        """160 karakteri aşan konu 'kısa ve öz' kuralından geçmemeli."""
        taslak = ORNEK_TASLAK.replace(
            "Park aydınlatması hakkında", "çok uzun konu " * 20
        )
        k = _kural(_denetle(taslak), "konu_kisa_oz")
        assert k is not None and k["durum"] is False


class TestBitisHiyerarsisi:
    """m.16/12: bitiş ifadesi ↔ muhatap hiyerarşisi tutarlılığı."""

    def test_ust_makama_arz_tutarli(self):
        """Müdürlükten Bakanlığa (üst) giden yazıda 'arz ederim' tutarlıdır."""
        k = _kural(_denetle(ORNEK_TASLAK), "bitis_hiyerarsi")
        assert k is not None, "Kademeler tespit edilebiliyor; kural eklenmeli"
        assert k["durum"] is True

    def test_ust_makama_rica_tutarsiz(self):
        """Üst makama 'rica ederim' m.16/12-a'ya aykırıdır."""
        taslak = ORNEK_TASLAK.replace(
            "Bilgilerinize arz ederim.", "Bilgilerinize rica ederim."
        )
        k = _kural(_denetle(taslak), "bitis_hiyerarsi")
        assert k is not None and k["durum"] is False
        assert "arz" in k["detay"]

    def test_alt_makama_rica_tutarli(self):
        """Valilikten (üst kuruluş) müdürlüğe (alt) 'rica ederim' tutarlıdır."""
        taslak = ORNEK_TASLAK.replace(
            "ÇEVRE, ŞEHİRCİLİK VE İKLİM DEĞİŞİKLİĞİ BAKANLIĞINA",
            "SARPDERE İLÇE MİLLİ EĞİTİM MÜDÜRLÜĞÜNE",
        ).replace("Bilgilerinize arz ederim.", "Bilgilerinize rica ederim.")
        k = _kural(_denetle(taslak), "bitis_hiyerarsi")
        assert k is not None and k["durum"] is True

    def test_kisi_muhatapta_kural_eklenmez(self):
        """'Sayın ...' muhataplı yazıda hiyerarşi kuralı eklenmemeli."""
        taslak = ORNEK_TASLAK.replace(
            "ÇEVRE, ŞEHİRCİLİK VE İKLİM DEĞİŞİKLİĞİ BAKANLIĞINA",
            "Sayın Kurgu Kişi",
        )
        assert _kural(_denetle(taslak), "bitis_hiyerarsi") is None


class TestKosulluKurallar:
    """Bağlam yokken koşullu kuralların eklenmediği testleri."""

    def test_maddeleme_yoksa_kural_eklenmez(self):
        assert _kural(_denetle(ORNEK_TASLAK), "maddeleme") is None

    def test_yanlis_maddeleme_uyari(self):
        """'a.' ve 'A)' biçimleri m.16/10'a aykırıdır; 'a)' uygundur."""
        taslak = ORNEK_TASLAK + "\na. birinci husus\nb) ikinci husus\n"
        k = _kural(_denetle(taslak), "maddeleme")
        assert k is not None and k["durum"] is False
        assert "a." in k["detay"]

    def test_dogru_maddeleme_gecer(self):
        taslak = ORNEK_TASLAK + "\na) birinci husus\nb) ikinci husus\n"
        k = _kural(_denetle(taslak), "maddeleme")
        assert k is not None and k["durum"] is True

    def test_yetki_devri_unvanli_gecer(self):
        """'Vali a.' satırının altında unvan varsa yetki devri düzeni uygundur."""
        taslak = ORNEK_TASLAK.replace(
            "(e-imzalıdır)\n                                                        Müdür",
            "(e-imzalıdır)\n                                                        Vali a.\n"
            "                                                        Vali Yardımcısı",
        )
        k = _kural(_denetle(taslak), "yetki_devri_unvan")
        assert k is not None and k["durum"] is True

    def test_yetki_devri_yoksa_kural_eklenmez(self):
        assert _kural(_denetle(ORNEK_TASLAK), "yetki_devri_unvan") is None


class TestGizlilikKisitliMod:
    """m.25: gizlilik dereceli evrakta kısıtlı mod testleri."""

    def test_gizlilik_damgasi_tespiti(self):
        """Tek başına satırdaki damga algılanmalı; gövde kelimesi algılanmamalı."""
        agent = DraftWriterAgent()
        assert agent._gizlilik_damgasi("Sayı : 1\n\nHİZMETE ÖZEL\n\nMetin") == "HİZMETE ÖZEL"
        assert agent._gizlilik_damgasi("bilgilerin gizliliği esastır") == ""

    def test_damgasiz_taslak_kuraldan_gecmez(self):
        """Gizlilik dereceli kaynakta damga taşımayan taslak uyarılmalı."""
        sonuc = _denetle(ORNEK_TASLAK, gizlilik="GİZLİ")
        k = _kural(sonuc, "gizlilik_kisitli")
        assert k is not None and k["durum"] is False

    def test_damgali_taslak_gecer(self):
        taslak = "GİZLİ\n" + ORNEK_TASLAK
        k = _kural(_denetle(taslak, gizlilik="GİZLİ"), "gizlilik_kisitli")
        assert k is not None and k["durum"] is True

    def test_gizlilikte_insan_onayi_isaretlenir(self):
        """Gizlilik damgalı kaynak evrak insan onayı gerektirmeli (kısıtlı mod)."""
        state = AgentState(raw_text="GİZLİ\n\nKonu : Deneme\nTest metni içeriği")
        state.classification = {"tur": "ust_yazi", "guven": 0.9}
        state = DraftWriterAgent().run(state)
        assert state.human_review_required is True
        assert any("m.25" in n for n in state.human_review_reasons)


class TestKapanisSecimi:
    """_resolve_kapanis hiyerarşi-farkında seçim testleri (m.16/12)."""

    def test_ust_makama_arz(self):
        """Müdürlükten Bakanlığa: arz (m.16/12-a: üst ve denk makama arz)."""
        kapanis = DraftWriterAgent()._resolve_kapanis(
            "cevap_yazisi", "ust_yazi",
            muhatap="KURGU BAKANLIĞINA", kurum_adi="Kurgu Müdürlüğü",
        )
        assert "arz ederim" in kapanis

    def test_denk_makama_arz(self):
        """Valilikten Valiliğe (denk): arz — 'eş makama rica' YANLIŞTIR."""
        kapanis = DraftWriterAgent()._resolve_kapanis(
            "cevap_yazisi", "ust_yazi",
            muhatap="KOMŞU İL VALİLİĞİNE", kurum_adi="Akçova Valiliği",
        )
        assert "arz ederim" in kapanis

    def test_alt_makama_rica(self):
        kapanis = DraftWriterAgent()._resolve_kapanis(
            "cevap_yazisi", "ust_yazi",
            muhatap="İLÇE MİLLİ EĞİTİM MÜDÜRLÜĞÜNE", kurum_adi="Kurgu Valiliği",
        )
        assert "rica ederim" in kapanis

    def test_kisiye_saygi(self):
        kapanis = DraftWriterAgent()._resolve_kapanis(
            "bilgilendirme", "dilekce", muhatap="Sayın Kurgu Kişi",
        )
        assert "Saygılarımla" in kapanis

    def test_belirsizde_tur_varsayilani(self):
        """Kademeler tespit edilemiyorsa tür-tabanlı davranış korunmalı."""
        kapanis = DraftWriterAgent()._resolve_kapanis("ust_yazi", "tutanak")
        assert "arz ederim" in kapanis


class TestCevapGonderenMuhatabi:
    """Cevap yazısı muhatabı, gelen evrakın GÖNDEREN birimine yönlendirilir.

    Gelen kurumsal evrakın anteti gönderen, muhatabı ise alıcı (=biz) olduğundan
    cevabın muhatabı gönderen birim olmalıdır; sistem cevabı kendine (gelen
    alıcıya) yazmamalı ve antet kurumu ile muhatap çakışmamalıdır.
    """

    def test_gonderen_birime_yonlendirilir(self):
        """Kurum-içi üst yazıya cevapta muhatap GÖNDEREN BİRİM olmalı (kendine değil)."""
        agent = DraftWriterAgent()
        extracted = {
            "muhatap": "MALİ HİZMETLER MÜDÜRLÜĞÜNE",  # gelen alıcı = biz
            "kurum_adlari": ["DOĞUŞEHİR BELEDİYE BAŞKANLIĞI", "Fen İşleri Müdürlüğü"],
        }
        sonuc = agent._cevap_gonderen_alici(extracted, "", "DOĞUŞEHİR BELEDİYE BAŞKANLIĞI")
        assert sonuc is not None
        muhatap, birim = sonuc
        assert muhatap == "FEN İŞLERİ MÜDÜRLÜĞÜNE"       # gönderen birim
        assert birim == "Mali Hizmetler Müdürlüğü"       # antet birimi = biz
        # Kendine yazışma yok: muhatap antet kurumuyla çakışmaz
        assert "BAŞKANLIĞI" not in muhatap

    def test_broadcast_muhatap_degistirilmez(self):
        """Dağıtım/broadcast gelen muhatapta düzeltme uygulanmaz (mevcut korunur)."""
        agent = DraftWriterAgent()
        extracted = {
            "muhatap": "DAĞITIM YERLERİNE",
            "kurum_adlari": ["AKÇOVA VALİLİĞİ", "İl Bilgi İşlem Müdürlüğü"],
        }
        assert agent._cevap_gonderen_alici(extracted, "", "AKÇOVA VALİLİĞİ") is None

    def test_gonderen_cikarilamazsa_mevcut_korunur(self):
        """Antet gönderen çıkarılamıyorsa (jenerik fallback) düzeltme uygulanmaz."""
        agent = DraftWriterAgent()
        extracted = {"muhatap": "GÜNEYKIYI BÖLGE MÜDÜRLÜĞÜNE", "kurum_adlari": []}
        assert agent._cevap_gonderen_alici(extracted, "", "GENEL MÜDÜRLÜK") is None
