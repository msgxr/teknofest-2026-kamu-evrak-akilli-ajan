# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Resmî yazı PDF üretici (src/utils/resmi_pdf.py) testleri.

Kapsam:
    - reportlab yoksa modül import edilebilir kalır ve `PDF_KULLANILABILIR`
      False olur (offline-first: PDF opsiyonel, çekirdek bozulmaz).
    - Üretilen çıktı geçerli bir PDF ikilisidir (%PDF- imzası).
    - İçerik paritesi: PDF metni, kaynak taslakla BİREBİR aynı kelimeleri
      taşır — hiçbir kelime düşmez, hiçbir kelime UYDURULMAZ (halüsinasyon
      yasağı; PDF yalnızca dizgiyi resmîleştirir, içerik eklemez/çıkarmaz).
    - Türkçe karakterler (ğ, ş, ı, İ, ç, ö, ü) PDF metninde korunur.

Not: PDF metin çıkarımı için pypdf (çekirdek bağımlılık) kullanılır; yoksa
o parite testleri atlanır (skip). reportlab yoksa üretim testleri atlanır.
"""

import re

import pytest

from src.utils import resmi_pdf

# reportlab kurulu değilse üretim testleri anlamsız — topluca atla.
reportlab_gerekli = pytest.mark.skipif(
    not resmi_pdf.PDF_KULLANILABILIR, reason="reportlab kurulu değil (opsiyonel)"
)

# Yönetmelik anatomisini taşıyan temsilî (kurgu) taslak.
ORNEK_TASLAK = """T.C.
DOĞUŞEHİR BELEDİYE BAŞKANLIĞI
Yazı İşleri Müdürlüğü

Sayı   : (TASLAK — sayı EBYS tarafından verilecektir)                                                13.07.2026
Konu   : Çamlık Parkı aydınlatma sorunu hakkında

Sayın Elif KOÇAK

İlgi   : 22/06/2026 tarihli dilekçeniz.

İlgi'de kayıtlı dilekçeniz incelenmiştir.

Talebiniz ilgili birimimizce değerlendirmeye alınmıştır.

Bilgilerinize sunulur.

Saygılarımla.

                                                        (e-imzalıdır)
                                                        Yazı İşleri Müdürü

Ek     : Yoktur.
"""


def _pdf_metni(pdf_bytes: bytes) -> str:
    """PDF'ten düz metin çıkarır (pypdf yoksa None döner)."""
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return None
    import io

    okuyucu = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((s.extract_text() or "") for s in okuyucu.pages)


def test_bayrak_ve_import():
    """Modül her koşulda import edilebilir; bayrak bool'dur."""
    assert isinstance(resmi_pdf.PDF_KULLANILABILIR, bool)


def test_reportlab_yoksa_hata():
    """reportlab yokken üretim çağrısı net bir RuntimeError yükseltir."""
    if resmi_pdf.PDF_KULLANILABILIR:
        pytest.skip("reportlab kurulu; bu dal test edilemez")
    with pytest.raises(RuntimeError):
        resmi_pdf.taslak_pdf_uret(ORNEK_TASLAK)


@reportlab_gerekli
def test_gecerli_pdf_uretilir():
    """Çıktı geçerli bir PDF ikilisidir (imza + makul boyut)."""
    pdf = resmi_pdf.taslak_pdf_uret(ORNEK_TASLAK)
    assert isinstance(pdf, (bytes, bytearray))
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000  # gömülü fontla birlikte anlamlı boyut


@reportlab_gerekli
def test_bos_taslak_da_uretir():
    """Boş/eksik metin çökme üretmez (kapı senaryoları için dayanıklılık)."""
    pdf = resmi_pdf.taslak_pdf_uret("")
    assert pdf[:5] == b"%PDF-"


@reportlab_gerekli
def test_icerik_paritesi_kelime_kaybi_yok():
    """PDF metni, kaynak taslağın tüm kelimelerini taşır; uydurma kelime yok."""
    pdf = resmi_pdf.taslak_pdf_uret(ORNEK_TASLAK)
    pdf_text = _pdf_metni(pdf)
    if pdf_text is None:
        pytest.skip("PDF metin çıkarımı için pypdf/PyPDF2 yok")

    def kelime_kumesi(s: str) -> set:
        return set(re.findall(r"[0-9A-Za-zçğıöşüÇĞİÖŞÜ']+", s))

    kaynak = kelime_kumesi(ORNEK_TASLAK)
    pdf_k = kelime_kumesi(pdf_text)
    kayip = kaynak - pdf_k
    fazla = pdf_k - kaynak
    assert not kayip, f"PDF'te kaybolan kelimeler: {sorted(kayip)}"
    assert not fazla, f"PDF'e eklenen (uydurma) kelimeler: {sorted(fazla)}"


def test_etiket_iki_nokta_zorunlu():
    """_ETIKET yalnızca 'Etiket : değer' alan satırlarını yakalar; alan-etiketi
    kelimesiyle BAŞLAYAN gövde cümlelerini (iki noktasız) YAKALAMAZ."""
    from src.utils.resmi_pdf import _ETIKET
    # Gerçek alan satırları (yakalanmalı):
    for s in ("Sayı   : X", "Konu   : Y", "İlgi   : Z", "Ek     : Yoktur.",
              "Dağıtım:", "Gereği : Genel Müdürlük", "Bilgi  : Yazı İşleri"):
        assert _ETIKET.match(s), f"alan satırı yakalanmadı: {s}"
    # Alan-etiketi kelimesiyle başlayan GÖVDE cümleleri (yakalanmamalı):
    for s in ("Konu hakkında yürütülecek işlemlerde dikkate alınmalıdır.",
              "İlgi'de kayıtlı dilekçeniz incelenmiştir.",
              "Ek ödeme talebiniz değerlendirilmiştir.",
              "Gereği yapılmak üzere sunulmuştur.",
              "Bilgi işlem altyapısı güncellenmektedir."):
        assert not _ETIKET.match(s), f"gövde cümlesi yanlışlıkla alan sanıldı: {s}"


def test_muhatap_hepsi_buyuk_tespiti():
    """Tümü-BÜYÜK kurum/makam hitabı muhatap sayılır (TÜM BİRİMLERE dahil);
    karışık-kip gövde ve 'Sayın …' bu ölçüte GİRMEZ."""
    from src.utils.resmi_pdf import _hepsi_buyuk
    for s in ("TÜM BİRİMLERE", "GENEL MÜDÜRLÜK MAKAMINA",
              "İLGİLİ BİRİMLERE", "İNSAN KAYNAKLARI MÜDÜRLÜĞÜNE"):
        assert _hepsi_buyuk(s), f"muhatap tanınmadı: {s}"
    for s in ("Sayın Elif KOÇAK", "İlgi'de kayıtlı dilekçeniz",
              "Bilgilerinize arz ederim.", "13.07.2026"):
        assert not _hepsi_buyuk(s), f"muhatap olmayan satır muhatap sanıldı: {s}"


def test_antet_bosluksuz_taslakta_da_ayrilir():
    """Antet ile gövde arasında boş satır olmasa bile antet doğru sınırlanır
    (ilk alan etiketine/muhataba kadar); T.C. ile başlamayan metinde antet yok."""
    from src.utils.resmi_pdf import _antet_bitis
    bosluksuz = ["T.C.", "GÖKPINAR ÜNİVERSİTESİ", "Bilgi İşlem Müdürlüğü",
                 "Sayı   : X   13.07.2026", "Konu   : Y"]
    assert _antet_bitis(bosluksuz) == 3
    bosluklu = ["T.C.", "AKÇOVA VALİLİĞİ", "", "Sayı   : X"]
    assert _antet_bitis(bosluklu) == 2
    assert _antet_bitis(["Doğrudan gövde metni.", "İkinci satır."]) == 0


def test_gomulu_font_mevcut_ve_turkce_tam():
    """Depoya gömülü serif font var ve Türkçe karakterleri tam kapsıyor
    (Windows-dışı ortamda taşınabilir, tam offline yedek)."""
    from src.utils.resmi_pdf import _GOMULU_FONT_DIZINI
    duz = _GOMULU_FONT_DIZINI / "DejaVuSerif.ttf"
    assert duz.exists(), "gömülü DejaVuSerif.ttf bulunamadı"
    if not resmi_pdf.PDF_KULLANILABILIR:
        pytest.skip("reportlab yok")
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("GomuluTest", str(duz)))
    cmap = pdfmetrics.getFont("GomuluTest").face.charToGlyph
    eksik = [c for c in "ĞğİıŞşÇçÖöÜü" if ord(c) not in cmap]
    assert not eksik, f"gömülü fontta eksik Türkçe glyph: {eksik}"


@reportlab_gerekli
def test_turkce_karakterler_korunur():
    """Türkçe'ye özgü karakterler PDF metninde bozulmadan yer alır."""
    pdf = resmi_pdf.taslak_pdf_uret(ORNEK_TASLAK)
    pdf_text = _pdf_metni(pdf)
    if pdf_text is None:
        pytest.skip("PDF metin çıkarımı için pypdf/PyPDF2 yok")
    # Antet ajan tarafından BÜYÜK harfe çevrilir (DOĞUŞEHİR); gövdede karışık
    # kip korunur (Müdürlüğü, Çamlık, dilekçeniz).
    for parca in ("DOĞUŞEHİR", "BAŞKANLIĞI", "Müdürlüğü", "Çamlık", "dilekçeniz"):
        assert parca in pdf_text, f"Türkçe parça PDF'te yok/bozuk: {parca}"
