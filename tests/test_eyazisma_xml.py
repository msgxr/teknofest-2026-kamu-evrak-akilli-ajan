"""e-Yazışma üstveri XML export (src/utils/eyazisma.uret_ustveri_xml) testleri."""

import xml.etree.ElementTree as ET

from src.utils.eyazisma import uret_ustveri_xml


def test_xml_temel_elemanlar():
    sonuc = {
        "siniflandirma": {"tur": "dilekce", "tur_adi": "Dilekçe"},
        "bilgi_cikarim": {
            "konu": "Bilgi edinme talebi",
            "ilgi_referanslari": ["01.01.2026 tarihli yazı"],
        },
        "onceliklendirme": {"oncelik": "normal"},
        "yonlendirme": {"birim": "Yazı İşleri", "birim_kodu": "yazi_isleri"},
    }
    xml = uret_ustveri_xml(sonuc)
    assert "<Ustveri" in xml
    assert "<Konu>Bilgi edinme talebi</Konu>" in xml
    assert "<Tur>dilekce</Tur>" in xml
    assert "<IlgiListesi>" in xml


def test_xml_parse_edilebilir_ve_yapisi():
    xml = uret_ustveri_xml({"siniflandirma": {"tur": "rapor"}})
    kok = ET.fromstring(xml)
    assert kok.tag == "Ustveri"
    assert kok.find("Belge/Tur").text == "rapor"
    # İvedilik varsayılanı ve muhatap düğümü bulunmalı
    assert kok.find("Belge/Ivedilik") is not None
    assert kok.find("Muhatap") is not None


def test_xml_ozel_karakter_kacisi():
    # XML özel karakteri (&, <) güvenle kaçırılmalı (ET otomatik yapar)
    xml = uret_ustveri_xml({"bilgi_cikarim": {"konu": "A & B < C"}})
    kok = ET.fromstring(xml)  # parse edilebiliyorsa kaçış doğru
    assert kok.find("Belge/Konu").text == "A & B < C"
