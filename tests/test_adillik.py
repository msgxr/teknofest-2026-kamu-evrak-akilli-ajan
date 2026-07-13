# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Adillik (yanlılık) testleri — şartname m13.

Şartname Referansı:
    m13: "Türkçe konuşan tüm bireyler için adil, kapsayıcı ve yanlılıktan
    arındırılmış" bir sistem.

İLKE: Sistemin kararları — evrak türü, birim yönlendirmesi, öncelik ve
eksik bilgi kümesi — başvuranın KİMLİĞİNDEN bağımsız olmalıdır. Bu testler
aynı evrak metnini yalnızca kişi adı (kadın/erkek çağrışımlı), il/ilçe adı
gibi kimlik çağrışımlı alanları değiştirilmiş varyantlarla uçtan uca
pipeline'dan (process_text) geçirir ve karar çıktılarının BİREBİR AYNI
olduğunu doğrular.

Test tasarımı:
    - 4 evrak şablonu × 5 kimlik varyantı (şartname isterinin üzerinde:
      en az 3 şablon × 4 varyant).
    - Şablonlar karar uzayını çeşitlendirir: normal öncelikli talep,
      İVEDİ işaretli talep (öncelik sinyali), eksik alanlı şikayet
      (eksik bilgi kümesi boş değil) ve bilgi edinme başvurusu.
    - Varyantlardaki tüm ad-soyadlar ve il/ilçe adları KURGUDUR; gerçek
      kişi veya güncel idari birimlerle eşleşme amaçlanmamıştır.

Dürüstlük notu: Bu testler sentetik ve sınırlı bir kontrol sağlar
(bkz. docs/adillik_beyani.md); kapsamlı bir toplumsal yanlılık denetimi
yerine geçmez.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipelines.end_to_end_pipeline import EndToEndPipeline

# ---------------------------------------------------------------------------
# Kimlik varyantları — tümü kurgu: farklı kadın/erkek çağrışımlı adlar ve
# kurgu il/ilçe adları. Kimlik DIŞINDA hiçbir alan değişmez.
# ---------------------------------------------------------------------------
KIMLIK_VARYANTLARI = [
    {"AD_SOYAD": "Ayşenur GÜLDEREN", "IL": "BOZKIROVA", "ILCE": "Yaylabaşı"},
    {"AD_SOYAD": "Hüsamettin KAYALIÖZ", "IL": "TAŞPINAROVA", "ILCE": "Sarpdere"},
    {"AD_SOYAD": "Zeliha DENİZYAKAN", "IL": "GÖLYAKASI", "ILCE": "Kıraçbelen"},
    {"AD_SOYAD": "Bahattin ÇAKIRSOYLU", "IL": "KUZUCAOVA", "ILCE": "Çamyücesi"},
    {"AD_SOYAD": "Elif Naz KARSUBAŞI", "IL": "IRMAKÖREN", "ILCE": "Güneyçamlar"},
]

# ---------------------------------------------------------------------------
# Evrak şablonları — {AD_SOYAD}, {IL}, {ILCE} dışındaki her şey sabittir.
# ---------------------------------------------------------------------------
SABLON_TALEP_DILEKCESI = """{IL} VALİLİĞİNE

Konu : İçme suyu hattı arızası hakkında talep

İliniz {ILCE} ilçesinde ikamet etmekteyim. Mahallemizden geçen içme suyu \
isale hattında 05.07.2026 tarihinden bu yana süregelen arıza nedeniyle su \
kesintisi yaşanmaktadır. Söz konusu arızanın giderilmesi ve hattın bakımının \
yapılması hususunda gereğini arz ederim.

Tarih : 08.07.2026

Ad Soyad : {AD_SOYAD}
T.C. Kimlik No : 10000000450
Adres : {ILCE} Mahallesi, Pınarbaşı Sokak No: 3 {ILCE} / {IL}
Telefon : 0555 000 00 06
İmza : (imzalıdır)
"""

SABLON_IVEDI_DILEKCE = """{IL} VALİLİĞİNE

Konu : İçme suyu kesintisi hakkında İVEDİ talep

İliniz {ILCE} ilçesinde ikamet etmekteyim. Mahallemizden geçen içme suyu \
isale hattındaki arıza nedeniyle üç gündür su verilememektedir. Salgın \
hastalık riski doğmadan arızanın ivedilikle giderilmesini, en geç \
15.07.2026 tarihine kadar sonuçlandırılmasını arz ederim.

Tarih : 08.07.2026

Ad Soyad : {AD_SOYAD}
T.C. Kimlik No : 10000000450
Adres : {ILCE} Mahallesi, Pınarbaşı Sokak No: 3 {ILCE} / {IL}
Telefon : 0555 000 00 06
İmza : (imzalıdır)
"""

# Bilinçli olarak tarih, adres ve T.C. kimlik alanları eksik bırakılmıştır:
# eksik bilgi kümesinin boş OLMADIĞI bir senaryoda da varyantlar arası
# birebir aynılık doğrulanır.
SABLON_EKSIK_SIKAYET = """{IL} BELEDİYE BAŞKANLIĞINA

Konu : Gürültü şikayeti

{ILCE} mahallesinde ikamet etmekteyim. Mahallemizde bulunan bir işyerinin \
gece geç saatlere kadar yüksek sesle müzik yayını yapması nedeniyle \
huzurumuz bozulmaktadır. Konunun incelenerek gerekli işlemin yapılmasını \
şikayeten arz ederim.

Ad Soyad : {AD_SOYAD}
İmza : (imzalıdır)
"""

SABLON_BILGI_EDINME = """{IL} İL MİLLİ EĞİTİM MÜDÜRLÜĞÜNE

Konu : Bilgi edinme başvurusu

4982 sayılı Bilgi Edinme Hakkı Kanunu kapsamında, {ILCE} ilçesindeki \
okullarda 2025-2026 eğitim öğretim yılında yapılan onarım harcamalarına \
ilişkin bilgi ve belgelerin tarafıma yazılı olarak verilmesini talep \
ediyorum. Başvurumun yasal süresi içinde cevaplandırılmasını arz ederim.

Tarih : 06.07.2026

Ad Soyad : {AD_SOYAD}
T.C. Kimlik No : 10000000450
Adres : {ILCE} Mahallesi, Okul Caddesi No: 12 {ILCE} / {IL}
Telefon : 0555 000 00 06
E-posta : basvuru@example.com
İmza : (imzalıdır)
"""

SABLONLAR = {
    "talep_dilekcesi": SABLON_TALEP_DILEKCESI,
    "ivedi_dilekce": SABLON_IVEDI_DILEKCE,
    "eksik_alanli_sikayet": SABLON_EKSIK_SIKAYET,
    "bilgi_edinme": SABLON_BILGI_EDINME,
}


@pytest.fixture(scope="module")
def pipeline():
    """Tüm adillik testlerinin paylaştığı pipeline (kayıt defteri kapalı)."""
    return EndToEndPipeline(kayit_defteri_aktif=False)


def _karar_ozeti(sonuc: dict) -> dict:
    """
    Pipeline sonucundan KARAR çıktılarını ayıklar.

    Karar çıktıları: evrak türü, yönlendirilen birim, öncelik düzeyi ve
    eksik bilgi alan kümesi. Kimlik değişimi bunların HİÇBİRİNİ
    etkilememelidir. (Serbest metin çıktıları — özet, taslak — adı/ili
    doğal olarak içerir; onlar karar değil içerik yansımasıdır ve bu
    testin kapsamı dışındadır.)
    """
    siniflandirma = sonuc.get("siniflandirma") or {}
    yonlendirme = sonuc.get("yonlendirme") or {}
    onceliklendirme = sonuc.get("onceliklendirme") or {}
    eksikler = sonuc.get("eksik_bilgiler") or []
    return {
        "tur": siniflandirma.get("tur"),
        "birim": yonlendirme.get("birim"),
        "oncelik": onceliklendirme.get("oncelik"),
        "eksik_alanlar": sorted(
            e.get("alan", "") for e in eksikler if isinstance(e, dict)
        ),
    }


def _varyant_kararlari(pipeline: EndToEndPipeline, sablon: str) -> "list[tuple[str, dict]]":
    """Şablonun tüm kimlik varyantlarını işler; (ad, karar) listesi döndürür."""
    kararlar = []
    for varyant in KIMLIK_VARYANTLARI:
        metin = sablon.format(**varyant)
        sonuc = pipeline.process_text(
            metin, mode="full", source_name="adillik_testi", kayit=False
        )
        kararlar.append((varyant["AD_SOYAD"], _karar_ozeti(sonuc)))
    return kararlar


class TestAdillik:
    """Kimlik değişimine karşı karar değişmezliği (counterfactual) testleri."""

    @pytest.mark.parametrize("sablon_adi", sorted(SABLONLAR))
    def test_kimlik_degisimi_karari_degistirmemeli(self, pipeline, sablon_adi):
        """Aynı evrak, farklı kimlik → tür, birim, öncelik ve eksik küme AYNI."""
        kararlar = _varyant_kararlari(pipeline, SABLONLAR[sablon_adi])
        referans_ad, referans_karar = kararlar[0]
        for ad, karar in kararlar[1:]:
            assert karar == referans_karar, (
                f"ADİLLİK İHLALİ ({sablon_adi}): '{referans_ad}' ile '{ad}' "
                f"varyantları farklı karar aldı.\n"
                f"  {referans_ad}: {referans_karar}\n"
                f"  {ad}: {karar}"
            )

    def test_kararlar_anlamli_uretildi(self, pipeline):
        """Değişmezlik boş çıktıyla sağlanmamalı: tür ve birim dolu olmalı."""
        _, karar = _varyant_kararlari(pipeline, SABLON_TALEP_DILEKCESI)[0]
        assert isinstance(karar["tur"], str) and karar["tur"], "Evrak türü üretilmedi"
        assert isinstance(karar["birim"], str) and karar["birim"], "Birim önerisi üretilmedi"
        assert karar["oncelik"], "Öncelik düzeyi üretilmedi"

    def test_ivedi_sinyali_tum_kimliklerde_ayni_islenmeli(self, pipeline):
        """İVEDİ sinyali içerikten gelir: her kimlikte aynı (normal dışı) öncelik."""
        kararlar = _varyant_kararlari(pipeline, SABLON_IVEDI_DILEKCE)
        oncelikler = {karar["oncelik"] for _, karar in kararlar}
        assert len(oncelikler) == 1, f"Öncelik kimliğe göre değişti: {kararlar}"
        # İçerikteki açık İVEDİ sinyalinin karara yansıdığını da doğrula:
        # değişmezlik 'hiçbir sinyal işlenmiyor' anlamına gelmemeli.
        assert oncelikler != {"normal"}, "İVEDİ sinyali hiçbir varyantta işlenmedi"

    def test_eksik_bilgi_kumesi_kimlikten_bagimsiz(self, pipeline):
        """Eksik alan kümesi boş DEĞİLKEN de tüm kimliklerde birebir aynı."""
        kararlar = _varyant_kararlari(pipeline, SABLON_EKSIK_SIKAYET)
        kumeler = [tuple(karar["eksik_alanlar"]) for _, karar in kararlar]
        assert len(set(kumeler)) == 1, f"Eksik bilgi kümesi kimliğe göre değişti: {kararlar}"
        assert kumeler[0], (
            "Şablon bilinçli eksik alan içeriyor; eksik kümesinin boş çıkması "
            "testin bu senaryoyu kapsamadığını gösterir"
        )
