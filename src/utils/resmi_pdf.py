# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Resmî Yazı PDF Üretici — taslak metnini Resmî Yazışmalarda Uygulanacak Usul
ve Esaslar Hakkında Yönetmelik (RG 10.06.2020/31151) görsel formatına döker.

Neden ayrı bir modül?
    `draft_writer_agent` taslağı DÜZ METİN olarak üretir; sağ hizalamayı
    (imza bloğu, tarih) boşluk dolgusuyla taklit eder. Bu yalnızca eşit
    genişlikli (monospace) gösterimde doğru görünür. Orantılı bir PDF
    fontunda boşluk dolgusu bozulur. Bu modül, ÜRETİLEN METNİ içerik
    kaynağı olarak alır (PDF içeriği .txt ile birebir aynı kalır) ve her
    mantıksal satırı Yönetmelik'in görsel diziliş kurallarına göre yeniden
    hizalar: antet ortalı, Sayı/Tarih aynı satırda (tarih sağda), Konu/İlgi
    solda, muhatap ortalı, metin iki yana yaslı, imza bloğu sağda, Ek/Dağıtım
    altta.

Yönetmelik dayanakları (görsel format):
    - Kağıt A4; yazı tipi Times New Roman 12 punto (m. ek kılavuz); yazı alanı
      kağıt kenarlarından 2,5 cm boşlukla düzenlenir.
    - Sayı/Tarih ve Konu alanları antetin altında; muhatap (…MAKAMINA /
      …MÜDÜRLÜĞÜNE veya "Sayın …") ortada; imza bloğu sağ altta (m.17).
    Metnin İÇERİĞİ zaten `draft_writer_agent` tarafından yönetmeliğe uygun
    (m.11 Sayı, m.13 Konu, m.17 imza) üretilir; bu modül yalnızca DİZGİyi
    resmîleştirir, içerik eklemez/çıkarmaz.

Tasarım / kısıtlar:
    - reportlab ÇEKİRDEK bağımlılık DEĞİLDİR (offline-first korunur):
      kurulu değilse `PDF_KULLANILABILIR` False olur, .txt yolu bozulmaz.
      Bağımlılık `requirements-optional.txt` içinde deklare edilir.
    - Font seçimi taşınabilir bir zincirdir: Times New Roman (Windows) →
      Liberation Serif (Linux) → depoya GÖMÜLÜ DejaVu Serif (assets/fonts/,
      tam offline, dış pakete bağlı değil). Hepsi SERİF ve Türkçe'yi
      (ğ, ş, ı, İ, ç, ö, ü) tam kapsar. Sans-serif fontlara sessiz düşüş
      YAPILMAZ; hiç serif font yoksa görünür hata verilir (dürüstlük).
    - Halüsinasyon/uydurma yasağı: sahte logo, mühür, gerçek sayı numarası
      EKLENMEZ; yalnızca üretilmiş metin dizilir. Sayı satırı taslak ibaresini
      olduğu gibi taşır ("… EBYS tarafından verilecektir").
"""

from __future__ import annotations

import glob
import io
import os
import re
from pathlib import Path
from typing import Optional

# --- reportlab: opsiyonel bağımlılık (çekirdek değil) ----------------------
try:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    PDF_KULLANILABILIR = True
except Exception:  # pragma: no cover - reportlab yoksa
    PDF_KULLANILABILIR = False


# ===========================================================================
#  Yönetmelik görsel format sabitleri
# ===========================================================================

# Yazı alanı, A4 kağıdın kenarlarından bu kadar boşlukla düzenlenir (2,5 cm).
KENAR_CM = 2.5
# Times New Roman 12 punto (Yönetmelik ek kılavuz).
GOVDE_PUNTO = 12
ANTET_PUNTO = 12
# Satır aralığı (leading): okunaklılık için ~1,25 kat.
GOVDE_LEADING = 15

# İmza bloğu tespiti: şablon, imza satırlarını bu kadar baştan boşlukla
# sağa iter; bu eşiği aşan girinti "imza bloğu" işaretidir.
_IMZA_GIRINTI_ESIGI = 20

# Depoya gömülü taşınabilir serif font dizini (proje kökü/assets/fonts).
# Sistem fontları (Times New Roman / Liberation Serif) yoksa buradaki DejaVu
# Serif kullanılır — her ortamda tam Türkçe + serif, tam offline.
_GOMULU_FONT_DIZINI = (
    Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
)

# Font kayıt adları (bir kez kaydedilir).
_FONT_DUZ = "ResmiYazi"
_FONT_KALIN = "ResmiYazi-Bold"
_font_kayitli = False


# --- Satır rolü tespit desenleri (Yönetmelik alan etiketleri + hitap) ------
# Alan etiketli satırlar (Sayı, Konu, İlgi, Ek, Dağıtım, Gereği, Bilgi).
# İki nokta ZORUNLU: draft_writer şablonları alan satırlarını daima
# "Etiket : değer" (Dağıtım için "Dağıtım:") biçiminde üretir. İki nokta
# aranmazsa, gövde cümleleri de yanlış eşleşir ("Konu hakkında …", "İlgi
# tutarsızlığı …", "Ek ödeme …", "Gereği yapılmak …") ve alan gibi sola
# yaslanıp iki-yana-yaslı gövde dizgisini bozar.
_ETIKET = re.compile(
    r"^\s*(Sayı|Konu|İlgi|Ek|Dağıtım|Gereği|Bilgi)\s*:", re.UNICODE
)
# Sayı satırının sonundaki tarih (gg.aa.yyyy) — sağa hizalanacak.
_SATIR_SONU_TARIH = re.compile(r"\s{2,}(\d{2}\.\d{2}\.\d{4})\s*$")
# Muhatap tespiti. Antet çözüldükten sonra gövdede yer alan, TÜMÜ BÜYÜK harf
# bağımsız bir satır kurum/makam yönelme hitabıdır (…MAKAMINA, …MÜDÜRLÜĞÜNE,
# …BAŞKANLIĞINA, TÜM BİRİMLERE). Belirli ekleri tek tek saymak yerine
# (kırılgan; "BİRİMLERE" gibi biçimleri kaçırır) "satırda hiç küçük harf yok"
# ölçütü kullanılır; bu, draft_writer_agent'ın morfolojik _HITAP_SONU desenini
# kapsayan daha sağlam bir üst kümedir. Gerçek kişi muhatabı ayrıca "Sayın …"
# ile yakalanır (karışık kip: ortalı ama düz).
_TR_KUCUK = frozenset("abcçdefgğhıijklmnoöprsştuüvwxyzq")
# Gerçek kişi muhatabı ("Sayın Ad SOYAD" / "Sn. …").
_MUHATAP_KISI = re.compile(r"^\s*(Sayın|Sn\.)\s", re.UNICODE)


def _hepsi_buyuk(cekirdek: str) -> bool:
    """Satır en az bir harf içerir ve hiç Türkçe küçük harf içermezse True
    (kurum/makam yönelme hitabı = muhatap işareti)."""
    return any(ch.isalpha() for ch in cekirdek) and not any(
        ch in _TR_KUCUK for ch in cekirdek
    )


def _font_dosyasi_bul() -> tuple[Optional[str], Optional[str]]:
    """Türkçe kapsamlı (düz, kalın) serif font yollarını taşınabilir bir
    zincirle bulur: Times New Roman → Liberation Serif → DejaVuSerif.

    Returns:
        (duz_yol, kalin_yol) — bulunamayan için None.
    """
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    adaylar = [
        # (düz, kalın) — Yönetmelik fontu Times New Roman önce
        (os.path.join(win, "times.ttf"), os.path.join(win, "timesbd.ttf")),
        (
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ),
    ]
    for duz, kalin in adaylar:
        if os.path.exists(duz):
            k = kalin if os.path.exists(kalin) else duz
            return duz, k

    # Garantili taşınabilir yedek: depoya gömülü DejaVu Serif (tam Türkçe,
    # SERİF, tam offline; matplotlib gibi dış pakete BAĞLI DEĞİL). Böylece
    # Windows-dışı minimal ortamlarda da sessizce sans-serif bir fonta düşüp
    # "serif/Times New Roman" biçim kuralı ihlal edilmez (dürüstlük).
    gomulu = _GOMULU_FONT_DIZINI / "DejaVuSerif.ttf"
    if gomulu.exists():
        kalin = _GOMULU_FONT_DIZINI / "DejaVuSerif-Bold.ttf"
        return str(gomulu), str(kalin if kalin.exists() else gomulu)

    # Son çare: matplotlib ile paketli DejaVuSerif (yine SERİF + Türkçe).
    try:
        import matplotlib

        mpl = os.path.join(
            os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf"
        )
        duz = os.path.join(mpl, "DejaVuSerif.ttf")
        kalin = os.path.join(mpl, "DejaVuSerif-Bold.ttf")
        if os.path.exists(duz):
            return duz, kalin if os.path.exists(kalin) else duz
    except Exception:
        pass

    # Not: reportlab ile paketli Vera SANS-SERİF olduğundan yönetmelik "serif"
    # kuralına aykırıdır; bilinçli olarak yedek zincirine ALINMAZ. Hiçbir serif
    # font bulunamazsa çağıran (_fontlari_kaydet) net bir hata yükseltir —
    # sessizce uyumsuz çıktı üretmek yerine görünür başarısızlık yeğlenir.
    return None, None


def _fontlari_kaydet() -> None:
    """Türkçe serif fontu (düz + kalın) bir kez reportlab'a kaydeder."""
    global _font_kayitli
    if _font_kayitli:
        return
    duz, kalin = _font_dosyasi_bul()
    if not duz:
        raise RuntimeError(
            "Türkçe destekli bir serif font (Times New Roman / DejaVu Serif) "
            "bulunamadı; PDF üretilemiyor."
        )
    pdfmetrics.registerFont(TTFont(_FONT_DUZ, duz))
    pdfmetrics.registerFont(TTFont(_FONT_KALIN, kalin))
    _font_kayitli = True


def _stiller() -> dict:
    """Yönetmelik format rollerine karşılık gelen paragraf stilleri."""
    ortak = dict(fontName=_FONT_DUZ, fontSize=GOVDE_PUNTO, leading=GOVDE_LEADING)
    return {
        "tc": ParagraphStyle("tc", alignment=TA_CENTER, **ortak),
        "kurum": ParagraphStyle(
            "kurum", fontName=_FONT_KALIN, fontSize=ANTET_PUNTO,
            leading=GOVDE_LEADING, alignment=TA_CENTER,
        ),
        "birim": ParagraphStyle("birim", alignment=TA_CENTER, **ortak),
        "alan": ParagraphStyle("alan", alignment=TA_LEFT, **ortak),
        "alan_sag": ParagraphStyle("alan_sag", alignment=TA_RIGHT, **ortak),
        "muhatap": ParagraphStyle(
            "muhatap", fontName=_FONT_KALIN, fontSize=GOVDE_PUNTO,
            leading=GOVDE_LEADING, alignment=TA_CENTER,
        ),
        "muhatap_kisi": ParagraphStyle(
            "muhatap_kisi", alignment=TA_CENTER, **ortak
        ),
        "govde": ParagraphStyle(
            "govde", alignment=TA_JUSTIFY, spaceAfter=6, **ortak
        ),
        "imza": ParagraphStyle(
            "imza", alignment=TA_RIGHT, leading=GOVDE_LEADING,
            fontName=_FONT_DUZ, fontSize=GOVDE_PUNTO,
        ),
        "ek": ParagraphStyle("ek", alignment=TA_LEFT, **ortak),
    }


def _kacis(metin: str) -> str:
    """Platypus Paragraph mini-HTML işaretlemesi için özel karakterleri kaçırır."""
    return (
        metin.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _antet_bitis(satirlar: list[str]) -> int:
    """Antet (T.C. / kurum / birim) bloğunun bittiği satır indeksi.

    Antet yalnızca 'T.C.' ile başlayan taslaklarda vardır. Blok, ilk boş
    satırda VEYA ilk alan etiketi (Sayı/Konu…) / muhatap satırında biter —
    hangisi önce gelirse. Böylece antet ile gövde arasında boş satır
    bırakmayan serbest-biçim (LLM) taslaklarda da antet ortalı/kalın
    dizilebilir; boş satır varsayımına bağlı kalınmaz.
    """
    ilk_dolu = next((s.strip() for s in satirlar if s.strip()), "")
    if ilk_dolu != "T.C.":
        return 0  # antetsiz taslak — tüm satırlar gövde/alan olarak dizilir
    for i, s in enumerate(satirlar):
        if i == 0:  # 'T.C.' satırı — antetin ilk satırı
            continue
        c = s.strip()
        if not c:
            return i
        # Sınır: ilk alan etiketi (Sayı/Konu…) veya kişi muhatabı. Tümü-BÜYÜK
        # ölçütü BURADA kullanılmaz; antetteki kurum adı da tümü-BÜYÜK olduğundan
        # anteti erken kesip yanlış böler.
        if _ETIKET.match(c) or _MUHATAP_KISI.match(c):
            return i
    return len(satirlar)


def taslak_pdf_uret(
    taslak_metni: str, *, baslik: str = "Resmî Yazı Taslağı"
) -> bytes:
    """Resmî yazı taslağı düz metnini Yönetmelik görsel formatında PDF'e çevirir.

    Args:
        taslak_metni: `draft_writer_agent` çıktısı (yazi_taslagi) — resmî
            yazı düz metni.
        baslik: PDF üstveri başlığı (belge içeriğine yazılmaz).

    Returns:
        PDF ikili içeriği (bytes) — Streamlit download_button'a doğrudan verilebilir.

    Raises:
        RuntimeError: reportlab kurulu değilse ya da uygun font yoksa.
    """
    if not PDF_KULLANILABILIR:
        raise RuntimeError(
            "PDF üretimi için 'reportlab' gerekli (requirements-optional.txt)."
        )
    _fontlari_kaydet()
    stil = _stiller()

    metin = (taslak_metni or "").replace("\r\n", "\n").replace("\r", "\n")
    satirlar = metin.split("\n")

    story: list = []
    icerik_gen = A4[0] - 2 * KENAR_CM * cm

    # 1) Antet: ilk boş satıra kadar olan satırlar (T.C. / kurum / birim).
    antet_son = _antet_bitis(satirlar)
    antet = [s.strip() for s in satirlar[:antet_son] if s.strip()]
    for idx, s in enumerate(antet):
        if idx == 0:  # T.C.
            st = stil["tc"]
        elif idx == 1:  # kurum adı → kalın
            st = stil["kurum"]
        else:  # birim ve altı → düz
            st = stil["birim"]
        story.append(Paragraph(_kacis(s), st))
    if antet:
        story.append(Spacer(1, 10))

    # 2) Gövde: antet sonrası satırlar rol rol dizilir.
    for ham in satirlar[antet_son:]:
        s = ham.rstrip()
        if not s.strip():
            story.append(Spacer(1, 6))
            continue

        girinti = len(ham) - len(ham.lstrip(" "))
        cekirdek = s.strip()

        # (a) Sayı satırı: sonundaki tarihi sağa al (iki hücreli tablo).
        if _ETIKET.match(cekirdek) and cekirdek.startswith("Sayı"):
            m = _SATIR_SONU_TARIH.search(s)
            if m:
                tarih = m.group(1)
                sol = s[: m.start()].strip()
                tablo = Table(
                    [[
                        Paragraph(_kacis(sol), stil["alan"]),
                        Paragraph(_kacis(tarih), stil["alan_sag"]),
                    ]],
                    colWidths=[icerik_gen * 0.72, icerik_gen * 0.28],
                )
                tablo.setStyle(
                    TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ])
                )
                story.append(tablo)
            else:
                story.append(Paragraph(_kacis(cekirdek), stil["alan"]))
            continue

        # (b) Diğer alan etiketleri (Konu / İlgi / Ek / Dağıtım / Gereği / Bilgi).
        if _ETIKET.match(cekirdek):
            story.append(Paragraph(_kacis(cekirdek), stil["alan"]))
            continue

        # (c) İmza bloğu: belirgin girintiyle sağa itilmiş satırlar.
        if girinti >= _IMZA_GIRINTI_ESIGI:
            story.append(Paragraph(_kacis(cekirdek), stil["imza"]))
            continue

        # (d) Gerçek kişi muhatabı ("Sayın …") → ortalı düz.
        if _MUHATAP_KISI.match(cekirdek):
            story.append(Paragraph(_kacis(cekirdek), stil["muhatap_kisi"]))
            continue
        # (e) Kurum/makam muhatabı (tümü BÜYÜK harf, ör. TÜM BİRİMLERE,
        #     …MAKAMINA) → ortalı kalın.
        if _hepsi_buyuk(cekirdek):
            story.append(Paragraph(_kacis(cekirdek), stil["muhatap"]))
            continue

        # (f) Kalan her şey: gövde metni (iki yana yaslı).
        story.append(Paragraph(_kacis(cekirdek), stil["govde"]))

    tampon = io.BytesIO()
    dok = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        leftMargin=KENAR_CM * cm,
        rightMargin=KENAR_CM * cm,
        topMargin=KENAR_CM * cm,
        bottomMargin=KENAR_CM * cm,
        title=baslik,
        author="Kamu Evrak Akıllı Ajan (taslak)",
    )
    dok.build(story)
    return tampon.getvalue()
