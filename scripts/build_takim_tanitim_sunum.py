#!/usr/bin/env python3
# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""AGENTRA TECH — Takım Tanıtım Sunumu üreticisi (siyah + gümüş marka kimliği).

TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (1. Senaryo) — Ön Değerlendirme
Formu için "takım tanıtım sunumu". Tasarım, AGENTRA TECH amblemine %100 sadıktır:
siyah zemin + metalik gümüş/grafit monokrom palet, ince harf-aralıklı zarif
tipografi, gerçek logo (presentations/assets/agentra_logo.png) gömülü. Renk yok.

Şartname m.3.1: bu aşama proje sunumu değildir; amaç takımın organizasyon yapısını,
ekip üyelerini ve görev dağılımını tanıtmaktır (sunum takım-önceliklidir).

Kullanım:
    pip install -r requirements-optional.txt
    python scripts/build_takim_tanitim_sunum.py
    # PDF: PowerPoint -> Dosya -> Farklı Kaydet -> PDF
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Inches, Pt
except ImportError:  # pragma: no cover
    print("HATA: python-pptx kurulu değil.\nKurulum: pip install -r requirements-optional.txt",
          file=sys.stderr)
    sys.exit(1)

PROJE_KOKU = Path(__file__).resolve().parent.parent
ASSET = PROJE_KOKU / "presentations" / "assets"
LOGO_FULL = ASSET / "agentra_logo.png"      # amblem + AGENTRA TECH + SINCE 2026
LOGO_EMBLEM = ASSET / "agentra_emblem.png"  # yalnızca gümüş swoosh
FULL_RATIO = 1013 / 357
EMBLEM_RATIO = 1013 / 228
TOPLAM_SLAYT = 10


# ----------------------------------------------------------------------------
# Siyah + gümüş monokrom palet (amblemden)
# ----------------------------------------------------------------------------
def C(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


BG = C("0E0F13")        # slayt zemini — amblemin siyahına yakın
PANEL = C("1A1C22")     # kart/panel zemini
PANEL2 = C("23262F")    # koyu başlık şeridi / alternatif satır
LINE = C("30333D")      # kenarlık
INK = C("EAEBEE")       # birincil metin (yumuşak beyaz)
MUTED = C("989EA8")     # ikincil metin (gümüş-gri)
SILVER = C("C9CDD4")    # birincil vurgu (parlak gümüş)
SILVER2 = C("AAB0B9")
GRAPH = C("5B616B")     # ikincil vurgu (grafit gri — 2 tonluk ayrım)
DARKTEXT = C("14151A")  # gümüş dolgu üzerindeki metin

DISP = "Segoe UI Semilight"   # zarif ince başlık
BODY = "Segoe UI"
SEMI = "Segoe UI Semibold"
MONO = "Consolas"
W_IN, H_IN = 13.333, 7.5


# ----------------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------------
def R(text, color=INK, bold=False, size=14, font=BODY, spc=0):
    return (text, color, bold, size, font, spc)


def P(runs, align=PP_ALIGN.LEFT, space_after=2, space_before=0, line=None):
    return {"runs": runs, "align": align, "space_after": space_after,
            "space_before": space_before, "line": line}


def write(tf, paras, anchor=MSO_ANCHOR.TOP, mL=6, mR=6, mT=4, mB=4):
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(mL); tf.margin_right = Pt(mR)
    tf.margin_top = Pt(mT); tf.margin_bottom = Pt(mB)
    for i, pa in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = pa.get("align", PP_ALIGN.LEFT)
        p.space_after = Pt(pa.get("space_after", 2))
        p.space_before = Pt(pa.get("space_before", 0))
        if pa.get("line"):
            p.line_spacing = pa["line"]
        for (txt, color, bold, size, font, spc) in pa["runs"]:
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(size); r.font.bold = bold
            r.font.color.rgb = color; r.font.name = font
            if spc:
                r._r.get_or_add_rPr().set("spc", str(int(spc * 100)))
    return tf


def _noshadow(sp):
    try:
        sp.shadow.inherit = False
    except Exception:
        pass


def rrect(slide, x, y, w, h, fill, line=None, line_w=1.0, radius=0.06):
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(x), Inches(y), Inches(w), Inches(h))
    try:
        sp.adjustments[0] = radius
    except Exception:
        pass
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    _noshadow(sp)
    return sp


def rect(slide, x, y, w, h, fill, line=None, line_w=1.0):
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    _noshadow(sp)
    return sp


def oval(slide, x, y, w, h, fill, line=None, line_w=1.0):
    sp = slide.shapes.add_shape(MSO_SHAPE.OVAL,
                                Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    _noshadow(sp)
    return sp


def shape_text(sp, paras, anchor=MSO_ANCHOR.MIDDLE, mL=6, mR=6, mT=3, mB=3):
    write(sp.text_frame, paras, anchor=anchor, mL=mL, mR=mR, mT=mT, mB=mB)


def textbox(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    write(tb.text_frame, paras, anchor=anchor, mL=0, mR=0, mT=0, mB=0)
    return tb


def picture(slide, path, x, y, w):
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))


def arrow(slide, x, y, w, h, color=GRAPH, direction="right"):
    sh = MSO_SHAPE.RIGHT_ARROW if direction == "right" else MSO_SHAPE.DOWN_ARROW
    sp = slide.shapes.add_shape(sh, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid(); sp.fill.fore_color.rgb = color
    sp.line.fill.background()
    try:
        sp.adjustments[0] = 0.55; sp.adjustments[1] = 0.55
    except Exception:
        pass
    _noshadow(sp)
    return sp


def node(slide, x, y, w, h, title, sub=None, fill=PANEL, tcolor=INK,
         line=LINE, tsize=14, ssize=10.5, radius=0.08):
    sp = rrect(slide, x, y, w, h, fill, line=line, line_w=1.25, radius=radius)
    paras = [P([R(title, tcolor, False, tsize, SEMI)], align=PP_ALIGN.CENTER, space_after=1)]
    if sub:
        paras.append(P([R(sub, tcolor, False, ssize, BODY)], align=PP_ALIGN.CENTER, space_after=0))
    shape_text(sp, paras, anchor=MSO_ANCHOR.MIDDLE)
    return sp


def pill(slide, x, y, w, h, text, fill=PANEL2, tcolor=SILVER, size=11, border=LINE):
    sp = rrect(slide, x, y, w, h, fill, line=border, line_w=1.0, radius=0.5)
    shape_text(sp, [P([R(text, tcolor, False, size, SEMI)], align=PP_ALIGN.CENTER,
                      space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
    return sp


def avatar(slide, x, y, d, initial):
    oval(slide, x, y, d, d, C("2E323B"), line=SILVER, line_w=1.25)
    shape_text(slide.shapes[-1], [P([R(initial, SILVER, False, int(d * 30), SEMI)],
               align=PP_ALIGN.CENTER, space_after=0)], anchor=MSO_ANCHOR.MIDDLE)


def kpi_tile(slide, x, y, w, h, big, unit, label, accent=SILVER):
    rrect(slide, x, y, w, h, PANEL, line=LINE, line_w=1.25, radius=0.05)
    rect(slide, x, y + 0.16, 0.08, h - 0.32, accent)
    runs = [R(big, SILVER, False, 34, DISP)]
    if unit:
        runs.append(R(" " + unit, SILVER, False, 16, DISP))
    textbox(slide, x + 0.3, y + 0.14, w - 0.38, 0.66, [P(runs)])
    textbox(slide, x + 0.32, y + h - 0.78, w - 0.44, 0.7,
            [P([R(label, MUTED, False, 12.5, BODY)], line=1.02)])


def card(slide, x, y, w, h, title, body_lines, accent=SILVER):
    rrect(slide, x, y, w, h, PANEL, line=LINE, line_w=1.25, radius=0.05)
    rect(slide, x, y, w, 0.08, accent)
    textbox(slide, x + 0.3, y + 0.3, w - 0.46, 0.5, [P([R(title, INK, False, 15, SEMI)])])
    paras = [P([R("—  ", SILVER, False, 13, SEMI), R(t, MUTED, False, 13, BODY)],
               space_after=5, line=1.05) for t in body_lines]
    textbox(slide, x + 0.3, y + 0.92, w - 0.52, h - 1.04, paras)


def pipeline_strip(slide, y, items, x0=0.62, total_w=12.09, h=0.72):
    n = len(items)
    gap = 0.32
    sw = (total_w - gap * (n - 1)) / n
    x = x0
    for i, t in enumerate(items):
        node(slide, x, y, sw, h, t, fill=PANEL, tcolor=INK, line=LINE, tsize=12.5, radius=0.08)
        x += sw
        if i < n - 1:
            arrow(slide, x + 0.02, y + h / 2 - 0.14, gap - 0.06, 0.28)
            x += gap


# ----------------------------------------------------------------------------
# Sayfa iskeleti
# ----------------------------------------------------------------------------
def new_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    bg.fill.solid(); bg.fill.fore_color.rgb = BG
    return slide


def header(slide, kicker, title):
    textbox(slide, 0.62, 0.46, 10.6, 0.34,
            [P([R(kicker.upper(), SILVER2, False, 12, BODY, spc=3.2)])])
    textbox(slide, 0.62, 0.78, 10.8, 0.82, [P([R(title, INK, False, 29, DISP, spc=0.3)])])
    picture(slide, LOGO_EMBLEM, 11.02, 0.5, 1.7)  # sağ üst gümüş amblem


def footer(slide, n):
    rect(slide, 0.62, 7.06, 12.1, 0.012, LINE)
    textbox(slide, 0.62, 7.12, 9.0, 0.3,
            [P([R("AGENTRA TECH", SILVER2, False, 9, BODY, spc=2.0),
                R("     TEKNOFEST 2026 · Yapay Zeka Dil Ajanları Yarışması · 1. Senaryo",
                  MUTED, False, 9, BODY)])])
    textbox(slide, 11.3, 7.12, 1.42, 0.3,
            [P([R(f"{n:02d} / {TOPLAM_SLAYT:02d}", MUTED, False, 9.5, BODY)], align=PP_ALIGN.RIGHT)])


# ----------------------------------------------------------------------------
# 01 — Kapak
# ----------------------------------------------------------------------------
LOGO_W = 6.0                       # kapak + kapanış logosu: AYNI genişlik
LOGO_X = (W_IN - LOGO_W) / 2       # tam yatay ortalı (aynı konum)
LOGO_Y = 1.55                      # kapak + kapanış: AYNI dikey konum


def slayt_kapak(prs):
    s = new_slide(prs)
    textbox(s, 0, 0.98, W_IN, 0.4,
            [P([R("TEKNOFEST 2026 · YAPAY ZEKA DİL AJANLARI YARIŞMASI", SILVER2, False, 13.5, BODY, spc=3.0)],
               align=PP_ALIGN.CENTER)])
    picture(s, LOGO_FULL, LOGO_X, LOGO_Y, LOGO_W)  # yükseklik ≈ 2.115
    textbox(s, 0, 3.98, W_IN, 1.05,
            [P([R("Takım Tanıtım Sunumu", INK, False, 26, DISP, spc=0.5)], align=PP_ALIGN.CENTER, space_after=5),
             P([R("Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi · 1. Senaryo",
                 MUTED, False, 16, BODY)], align=PP_ALIGN.CENTER)])
    chips = ["4 Üye · 1 Kaptan", "Kuruluş 2026", "Açık Kaynak"]
    widths = [0.5 + len(ch) * 0.11 for ch in chips]
    gap = 0.24
    cx = (W_IN - (sum(widths) + gap * (len(chips) - 1))) / 2
    for ch, wch in zip(chips, widths):
        pill(s, cx, 5.62, wch, 0.48, ch, fill=PANEL, tcolor=SILVER2, size=13, border=LINE)
        cx += wch + gap
    textbox(s, 0, 6.52, W_IN, 0.5,
            [P([R("Takım Kaptanı: Şeyma Nur Çebi", SILVER2, False, 14, BODY),
                R("     ·     Temmuz 2026", MUTED, False, 14, BODY)], align=PP_ALIGN.CENTER)])
    return s


# ----------------------------------------------------------------------------
# 02 — Kısaca Biz
# ----------------------------------------------------------------------------
def slayt_kunye(prs, n):
    s = new_slide(prs)
    header(s, "Takımımız", "Kısaca Biz")
    tiles = [
        ("4", "", "Takım üyesi"),
        ("1", "", "Takım kaptanı"),
        ("2026", "", "Kuruluş yılı"),
        ("3", "", "Farklı üniversite · 3 mühendislik dalı"),
        ("Açık", "", "Kaynak · Apache 2.0 · tamamı Türkçe"),
    ]
    x = 0.62; tw = 2.36
    for (big, unit, label) in tiles:
        kpi_tile(s, x, 1.9, tw, 1.55, big, unit, label)
        x += tw + 0.11
    rrect(s, 0.62, 3.72, 12.09, 1.5, PANEL, line=LINE, line_w=1.25, radius=0.05)
    rect(s, 0.62, 3.72, 0.08, 1.5, SILVER)
    textbox(s, 0.98, 3.98, 11.5, 1.2,
            [P([R("Biz ", INK, False, 16, BODY), R("AGENTRA TECH", SILVER, False, 16.5, SEMI),
                R("; TEKNOFEST 2026 için bir araya gelen, ", INK, False, 16, BODY),
                R("Türkçe dil teknolojileri ve akıllı ajan sistemleri", SILVER, False, 16, SEMI),
                R(" üzerine çalışan 4 kişilik bir öğrenci takımıyız.", INK, False, 16, BODY)], line=1.16),
             P([R("Adımızın merkezinde “agent” var: kararları izlenebilir, tamamen açık kaynak bir sistem geliştiriyoruz.",
                 MUTED, False, 13.5, BODY)], space_before=6)])
    textbox(s, 0.62, 5.78, 12.0, 0.4,
            [P([R("Şartname m.3.1: bu sunum takımın organizasyon yapısını, ekip üyelerini ve görev dağılımını tanıtır.",
                 MUTED, False, 12, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 03 — Kuruluş, Amaç & Değerler
# ----------------------------------------------------------------------------
def slayt_kimlik(prs, n):
    s = new_slide(prs)
    header(s, "Kimliğimiz", "Kuruluşumuz, Amacımız ve Değerlerimiz")
    rrect(s, 0.62, 1.82, 6.35, 4.6, PANEL, line=LINE, line_w=1.25, radius=0.05)
    rect(s, 0.62, 1.82, 0.08, 4.6, SILVER)
    textbox(s, 0.98, 2.02, 5.85, 0.45, [P([R("Kuruluş & Amaç", INK, False, 18, SEMI)])])
    textbox(s, 0.98, 2.64, 5.9, 3.7,
            [P([R("Kuruluş: ", SILVER, False, 14, SEMI), R("2026", INK, False, 14, SEMI),
                R("   ·   4 kişilik öğrenci takımı", MUTED, False, 13, BODY)], space_after=10),
             P([R("Takım adı: ", SILVER, False, 14, SEMI),
                R("AGENTRA TECH — merkezinde “agent” (ajan) odağı vardır.",
                  INK, False, 13.5, BODY)], space_after=10, line=1.12),
             P([R("Amacımız", SILVER, False, 14, SEMI)], space_after=4),
             P([R("Kamu evrak ve yazışma süreçlerini okuyan, anlayan, eksiğini bulan, mevzuat öneren, "
                  "resmî yazı taslaklayıp doğru birime yönlendiren; çok ajanlı, offline-first ve yerli "
                  "bir yapay zekâ sistemiyle uçtan uca otomatikleştirmek.",
                  INK, False, 13.5, BODY)], line=1.18)])
    textbox(s, 7.2, 1.96, 5.5, 0.45, [P([R("Değerlerimiz", INK, False, 18, SEMI)])])
    vals = [
        ("Güvenilirlik", "Her karar bir güven skoruyla gelir."),
        ("Şeffaflık", "Her öneri gerekçe ve madde dayanağı taşır."),
        ("Veri Koruması (KVKK)", "Kişisel veri sızdırılmaz; yerli ve offline."),
        ("Dürüstlük", "Ölçümler ne çıkarsa olduğu gibi raporlanır."),
    ]
    y = 2.6
    for (tt, bd) in vals:
        rrect(s, 7.2, y, 5.5, 0.92, PANEL, line=LINE, line_w=1.25, radius=0.06)
        rect(s, 7.2, y, 0.08, 0.92, SILVER)
        textbox(s, 7.44, y + 0.14, 5.1, 0.4, [P([R(tt, INK, False, 14.5, SEMI)])])
        textbox(s, 7.44, y + 0.52, 5.05, 0.35, [P([R(bd, MUTED, False, 12, BODY)])])
        y += 1.02
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 04 — Organizasyon Yapısı
# ----------------------------------------------------------------------------
def slayt_organizasyon(prs, n):
    s = new_slide(prs)
    header(s, "Organizasyon Yapısı", "Takımı Nasıl Örgütledik?")
    tw = 5.6
    tx = (W_IN - tw) / 2
    rrect(s, tx, 1.78, tw, 0.9, PANEL2, line=SILVER, line_w=1.25, radius=0.06)
    shape_text(s.shapes[-1],
               [P([R("AGENTRA TECH", SILVER, False, 18, SEMI, spc=1.5)], align=PP_ALIGN.CENTER, space_after=1),
                P([R("4 kişilik takım · Kuruluş 2026", MUTED, False, 12, BODY)],
                  align=PP_ALIGN.CENTER, space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
    people = [
        ("Ş", "Şeyma Nur Çebi", "İçerik Analizi &\nDeğerlendirme", True),
        ("M", "Muhammed Sina Gün", "Mimari &\nOrkestrasyon", False),
        ("Z", "Zeynep Akel", "Etkileşim · Yönlendirme\n· KVKK", False),
        ("E", "Emine Elik", "Veri · Test ·\nDoküman · Sunum", False),
    ]
    bw = 2.86; gap = (12.09 - 4 * bw) / 3
    xs = [0.62 + i * (bw + gap) for i in range(4)]
    centers = [x + bw / 2 for x in xs]
    top_cx = tx + tw / 2
    bus_y = 3.28
    box_y = 3.74
    seg = lambda x, y, w, h: rect(s, x, y, w, h, GRAPH)
    seg(top_cx - 0.012, 2.68, 0.024, bus_y - 2.68)
    seg(min(centers) - 0.012, bus_y, (max(centers) - min(centers)) + 0.024, 0.024)
    for cx in centers:
        seg(cx - 0.012, bus_y, 0.024, box_y - bus_y)
    bh = 2.1
    for (ini, nm, fn, cap), x in zip(people, xs):
        rrect(s, x, box_y, bw, bh, PANEL, line=LINE, line_w=1.25, radius=0.06)
        rect(s, x, box_y, bw, 0.08, SILVER if cap else GRAPH)
        avatar(s, x + bw / 2 - 0.36, box_y + 0.24, 0.72, ini)
        textbox(s, x + 0.1, box_y + 1.06, bw - 0.2, 0.4,
                [P([R(nm, INK, False, 14, SEMI)], align=PP_ALIGN.CENTER, line=0.98)])
        paras = [P([R(seg_, MUTED, False, 12, BODY)], align=PP_ALIGN.CENTER, space_after=0, line=1.02)
                 for seg_ in fn.split("\n")]
        textbox(s, x + 0.08, box_y + 1.5, bw - 0.16, 0.6, paras)
        if cap:
            pill(s, x + bw / 2 - 0.74, box_y - 0.18, 1.48, 0.36, "★ TAKIM KAPTANI",
                 fill=SILVER, tcolor=DARKTEXT, size=10, border=None)
    rrect(s, 0.62, 6.16, 12.09, 0.74, PANEL, line=LINE, line_w=1.25, radius=0.06)
    textbox(s, 0.98, 6.3, 11.5, 0.5,
            [P([R("Kaptan Şeyma Nur Çebi ekibi koordine eder; kararlar ortak GitHub deposu üzerinden "
                  "şeffaf yürür. Her uzmanlık alanı bir sorumluya bağlıdır.",
                  INK, False, 12.5, BODY)], line=1.05)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 05 — Takım Üyeleri
# ----------------------------------------------------------------------------
def slayt_uyeler(prs, n):
    s = new_slide(prs)
    header(s, "Ekip & Organizasyon", "Ekibimiz")
    members = [
        ("Şeyma Nur Çebi", "TAKIM KAPTANI · YAZILIM", "Yazılım Müh. · 3. Sınıf · Arel Üni.",
         "Görev 1 içerik analizi: sınıflandırma, bilgi çıkarımı, mevzuat RAG; değerlendirme ve entegrasyon.", True),
        ("Muhammed Sina Gün", "YAZILIM", "Bilgisayar Müh. · 3. Sınıf · Arel Üni.",
         "Mimari ve orkestrasyon; model-agnostik LLM katmanı; Görev 2 taslak üretimi (OCR, özet).", False),
        ("Emine Elik", "VERİ · TEST · DOKÜMAN", "Maden Müh. · 1. Sınıf · Cerrahpaşa Üni.",
         "Veri seti ve etiketleme; test kapsamı; dokümantasyon; sunum ve demo; şartname uyumu.", False),
        ("Zeynep Akel", "YAZILIM", "Yazılım Müh. · 3. Sınıf · Biruni Üni.",
         "Görev 1 eksik bilgi; Görev 2 yönlendirme ve kullanıcı etkileşimi; triyaj, KVKK; web arayüzü.", False),
    ]
    pos = [(0.62, 1.68), (6.72, 1.68), (0.62, 4.16), (6.72, 4.16)]
    cw, ch = 6.0, 2.36
    for (name, role, akademik, desc, cap), (x, y) in zip(members, pos):
        rrect(s, x, y, cw, ch, PANEL, line=LINE, line_w=1.25, radius=0.05)
        rect(s, x, y, 0.1, ch, SILVER if cap else GRAPH)
        avatar(s, x + 0.32, y + 0.4, 0.86, name[0])
        textbox(s, x + 1.42, y + 0.34, cw - 1.6, 0.42, [P([R(name, INK, False, 17.5, SEMI)])])
        textbox(s, x + 1.44, y + 0.86, cw - 1.6, 0.34, [P([R(akademik, SILVER, False, 12, SEMI)])])
        pill(s, x + 1.44, y + 1.22, min(cw - 1.6, 0.6 + len(role) * 0.098), 0.34, role, size=10.5)
        textbox(s, x + 0.34, y + 1.7, cw - 0.62, 0.62,
                [P([R(desc, MUTED, False, 12.5, BODY)], line=1.06)])
        if cap:
            pill(s, x + cw - 1.5, y + 0.28, 1.3, 0.36, "★ KAPTAN", fill=SILVER,
                 tcolor=DARKTEXT, size=10.5, border=None)
    textbox(s, 0.62, 6.58, 12.1, 0.4,
            [P([R("Takım kaptanı Şeyma Nur Çebi ekibi koordine eder · her uzmanlık alanı bir sorumluya bağlıdır · 3 üniversite, 3 mühendislik dalı.",
                 MUTED, False, 12, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 06 — Görev Dağılımı
# ----------------------------------------------------------------------------
def slayt_gorev_dagilimi(prs, n):
    s = new_slide(prs)
    header(s, "Görev Dağılımı", "Görev Dağılımımız · Şartname m.6.4")

    def panel(x, w, title, accent, rows):
        rrect(s, x, 1.72, w, 4.12, PANEL, line=LINE, line_w=1.25, radius=0.05)
        rrect(s, x, 1.72, w, 0.56, PANEL2, line=None, radius=0.05)
        rect(s, x, 2.1, w, 0.16, PANEL2)
        rect(s, x, 1.72, w, 0.05, accent)
        textbox(s, x, 1.76, w, 0.5, [P([R(title, SILVER, False, 13.5, SEMI)],
                align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
        ry = 2.42
        for j, (cap, who) in enumerate(rows):
            if j % 2 == 1:
                rect(s, x + 0.12, ry, w - 0.24, 0.55, PANEL2)
            textbox(s, x + 0.3, ry + 0.14, w - 2.0, 0.34, [P([R(cap, INK, False, 13, BODY)])])
            pw = 0.44 + len(who) * 0.1
            pill(s, x + w - pw - 0.28, ry + 0.11, pw, 0.34, who, size=10.5)
            ry += 0.565

    panel(0.62, 6.0, "GÖREV 1 — Sınıflandırma & İçerik Analizi", SILVER, [
        ("OCR / metin okuma", "Sina"),
        ("Tür belirleme (sınıflandırma)", "Şeyma Nur"),
        ("Bilgi çıkarımı", "Şeyma Nur"),
        ("Eksik bilgi tespiti", "Zeynep"),
        ("Mevzuat önerisi (BM25 RAG)", "Şeyma Nur"),
        ("Özet oluşturma", "Sina"),
    ])
    panel(6.72, 6.0, "GÖREV 2 — Taslaklama & Yönlendirme", GRAPH, [
        ("Resmî yazı taslağı", "Sina"),
        ("Format öz-denetimi (üslup)", "Sina"),
        ("Birim yönlendirme", "Zeynep"),
        ("Kullanıcı bilgilendirme", "Zeynep"),
        ("Eksik bilgi talebi", "Zeynep"),
        ("Altyapı: veri · test · doküman", "Emine"),
    ])
    textbox(s, 0.62, 5.98, 12.0, 0.4,
            [P([R("Her yetenek bir sorumluya ve gerçek bir kod modülüne bağlıdır.",
                 MUTED, False, 12, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 07 — Nasıl Çalışıyoruz
# ----------------------------------------------------------------------------
def slayt_calisma(prs, n):
    s = new_slide(prs)
    header(s, "Çalışma Biçimimiz", "Nasıl Çalışıyoruz?")
    pipeline_strip(s, 2.02, ["Fikir", "Geliştirme", "Test & Ölçüm", "Dürüst Rapor", "İyileştirme"], h=0.78)
    textbox(s, 0.62, 2.98, 12.0, 0.4,
            [P([R("Her özellik; fikirden koda, otomatik testlere ve dürüst ölçüme kadar aynı döngüden geçer.",
                 MUTED, False, 12.5, BODY)], align=PP_ALIGN.CENTER)])
    cards = [
        ("Açık ve İzlenebilir", ["Ortak GitHub deposu (Apache 2.0)",
         "Her karar kayıt altında", "Tüm dokümantasyon Türkçe"]),
        ("Sürekli Entegrasyon", ["En az haftalık commit",
         "500+ otomatik test yeşil", "Her katkı gözden geçirilir"]),
        ("Dürüst Ölçüm", ["Düzenli değerlendirme ölçümü",
         "Tutulmuş (held-out) setler", "Sonuçlar olduğu gibi raporlanır"]),
    ]
    x = 0.62; cw = 3.93
    for (tt, bl) in cards:
        card(s, x, 3.58, cw, 2.96, tt, bl)
        x += cw + 0.14
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 08 — Projemiz (kısa)
# ----------------------------------------------------------------------------
def slayt_proje(prs, n):
    s = new_slide(prs)
    header(s, "Kısa Proje Tanıtımı", "Ne Geliştiriyoruz?")
    rrect(s, 0.62, 1.78, 12.09, 1.16, PANEL, line=LINE, line_w=1.25, radius=0.05)
    rect(s, 0.62, 1.78, 0.08, 1.16, SILVER)
    textbox(s, 0.98, 1.92, 11.5, 0.95,
            [P([R("Kamu kurumlarına gelen evrağı ", INK, False, 15.5, BODY),
                R("okuyan · anlayan · eksiğini bulan · mevzuat öneren · taslaklayan · yönlendiren",
                  SILVER, False, 15.5, SEMI),
                R(" çok ajanlı bir yapay zekâ sistemi.", INK, False, 15.5, BODY)], line=1.12),
             P([R("11 uzman ajan + orkestratör · framework bağımsız saf Python · çevrimdışı-öncelikli",
                 MUTED, False, 12.5, BODY)], space_before=4)])
    pipeline_strip(s, 3.24, ["Girdi", "Orkestratör", "Görev 1", "Görev 2", "12+ Çıktı"], h=0.76)
    card(s, 0.62, 4.3, 5.95, 2.08, "Görev 1 — Sınıflandırma & İçerik",
         ["Metin/PDF/görüntü okuma (OCR) + tür belirleme",
          "Bilgi çıkarımı · eksik bilgi tespiti",
          "Mevzuat önerisi · kısa özet"])
    card(s, 6.76, 4.3, 5.95, 2.08, "Görev 2 — Taslaklama & Yönlendirme",
         ["Resmî yazı taslağı (Yönetmelik uyumlu)",
          "Gerekçeli birim yönlendirme",
          "Kullanıcı bilgilendirme · eksik bilgi talebi"], accent=GRAPH)
    textbox(s, 0.62, 6.56, 12.1, 0.4,
            [P([R("Ayrıntılı teknik mimari, kod ve canlı demo final aşamasında sunulacaktır.",
                 MUTED, False, 12, BODY)], align=PP_ALIGN.CENTER)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 09 — Kanıtımız
# ----------------------------------------------------------------------------
def slayt_kanit(prs, n):
    s = new_slide(prs)
    header(s, "Kanıtımız", "Bugüne Kadar Ne Ürettik?")
    tiles = [
        ("✓", "", "Çalışan sistem · CLI + web arayüzü + demo"),
        ("500", "+", "Test — sürekli entegrasyonda yeşil"),
        ("116", "", "Etiketli sentetik kurgu evrak"),
        ("0", "", "KVKK sızıntısı (bağımsız denetim)"),
    ]
    x = 0.62; tw = 2.97
    for (big, unit, label) in tiles:
        kpi_tile(s, x, 1.9, tw, 1.55, big, unit, label)
        x += tw + 0.12

    def olcum(x, w, title, accent, rows):
        rrect(s, x, 3.7, w, 2.16, PANEL, line=LINE, line_w=1.25, radius=0.05)
        rect(s, x, 3.7, w, 0.08, accent)
        textbox(s, x + 0.26, 3.92, w - 0.42, 0.4, [P([R(title, INK, False, 14, SEMI)])])
        paras = [P([R(lbl + "   ", MUTED, False, 13, BODY), R(val, SILVER, False, 13, SEMI)],
                   space_after=6) for (lbl, val) in rows]
        textbox(s, x + 0.26, 4.44, w - 0.46, 1.4, paras)

    olcum(0.62, 5.95, "Geliştirme seti · 52 evrak", SILVER, [
        ("Sınıflandırma doğruluğu", "1,00"), ("Birim yönlendirme", "0,96"),
        ("Eksik-bilgi tespiti (F1)", "1,00"), ("Mevzuat isabet@3", "0,96"),
    ])
    olcum(6.77, 5.95, "Adversarial tutulmuş set · 16 evrak", GRAPH, [
        ("Sınıflandırma doğruluğu", "0,94"), ("Birim yönlendirme", "1,00"),
        ("Eksik-bilgi tespiti (F1)", "0,83"), ("Mevzuat isabet@3", "0,94"),
    ])
    textbox(s, 0.62, 6.02, 12.1, 0.4,
            [P([R("Kaynak: ", MUTED, False, 11.5, SEMI),
                R("eval_report*.json", SILVER2, False, 11.5, MONO),
                R("  ·  tamamen çevrimdışı mod  ·  sonuçlar olduğu gibi raporlanır  ·  Apache 2.0",
                  MUTED, False, 11.5, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 10 — Motivasyon
# ----------------------------------------------------------------------------
def slayt_motivasyon(prs, n):
    s = new_slide(prs)
    header(s, "Neden Buradayız?", "Katılım Motivasyonumuz")
    items = [
        ("Ölçülebilir verimlilik", "İlk inceleme, taslak ve yönlendirme adımlarında personel zamanı kazanımı."),
        ("Veri egemenliği & KVKK", "Kişisel veriyi 3. taraf API'ye sızdırmadan, tamamen yerel çalışan yerli çözüm."),
        ("Açık kaynak katkısı", "Türkçe dil teknolojileri ekosistemine (TAKP) Apache 2.0 lisanslı katkı."),
        ("Sorumlu otomasyon", "Emin olmadığı kararda durup insana devreden, gerekçeli ve denetlenebilir tasarım."),
        ("Takımın ilgisi", "Türkçe NLP ve kamu süreçlerine dair merak ve ortak çalışma isteği."),
    ]
    pos = [(0.62, 1.8), (4.66, 1.8), (8.7, 1.8), (0.62, 4.06), (4.66, 4.06)]
    cw, ch = 3.9, 2.08
    for (tt, bd), (x, y) in zip(items, pos):
        rrect(s, x, y, cw, ch, PANEL, line=LINE, line_w=1.25, radius=0.06)
        rect(s, x, y, cw, 0.08, SILVER)
        textbox(s, x + 0.3, y + 0.34, cw - 0.5, 0.6, [P([R(tt, INK, False, 15, SEMI)], line=1.0)])
        textbox(s, x + 0.3, y + 1.02, cw - 0.54, 0.95, [P([R(bd, MUTED, False, 12.5, BODY)], line=1.1)])
    rrect(s, 8.7, 4.06, 3.9, 2.08, SILVER, line=None, radius=0.06)
    textbox(s, 8.98, 4.28, 3.42, 1.75,
            [P([R("Kamuya uygun yapay zekâ", DARKTEXT, False, 15.5, SEMI)], space_after=5),
             P([R("“Her şeyi otomatikleştiren” değil; ", DARKTEXT, False, 13, BODY),
                R("doğru yerde insana devreden", DARKTEXT, True, 13, SEMI),
                R(" bir sistem güven verir.", DARKTEXT, False, 13, BODY)], line=1.12)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 11 — Kapanış
# ----------------------------------------------------------------------------
def slayt_kapanis(prs, n):
    s = new_slide(prs)
    textbox(s, 0, 1.02, W_IN, 0.4,
            [P([R("TEŞEKKÜRLER", SILVER2, False, 14, BODY, spc=3.2)], align=PP_ALIGN.CENTER)])
    picture(s, LOGO_FULL, LOGO_X, LOGO_Y, LOGO_W)  # kapak ile AYNI konum/boyut
    textbox(s, 0, 3.98, W_IN, 0.5,
            [P([R("Organizasyon yapısı, ekip ve görev dağılımıyla; kamuya uygun bir yapay zekâ takımı.",
                 MUTED, False, 15, BODY)], align=PP_ALIGN.CENTER)])
    depo_w = 9.4
    depo_x = (W_IN - depo_w) / 2
    rrect(s, depo_x, 4.86, depo_w, 0.74, PANEL, line=LINE, line_w=1.0, radius=0.08)
    textbox(s, depo_x, 5.03, depo_w, 0.44,
            [P([R("Depo:  ", SILVER2, False, 13.5, SEMI),
                R("github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan", INK, False, 13.5, MONO)],
               align=PP_ALIGN.CENTER)])
    textbox(s, 0, 6.05, W_IN, 0.5,
            [P([R("Kamuya uygun, dürüst, açık kaynak ve ", MUTED, False, 15, BODY),
                R("bugün çalışan", INK, False, 15, SEMI),
                R(" bir sistem geliştiren bir takımız.", MUTED, False, 15, BODY)], align=PP_ALIGN.CENTER)])
    return s


def uret(cikti: Path):
    prs = Presentation()
    prs.slide_width = Inches(W_IN)
    prs.slide_height = Inches(H_IN)
    prs.core_properties.author = "AGENTRA TECH"
    prs.core_properties.last_modified_by = "AGENTRA TECH"
    prs.core_properties.title = "AGENTRA TECH — Takım Tanıtım Sunumu (TEKNOFEST 2026 TYDA · 1. Senaryo)"

    slayt_kapak(prs)
    slayt_kunye(prs, 2)
    slayt_kimlik(prs, 3)
    slayt_uyeler(prs, 4)          # Ekibimiz — organizasyon şeması ile birleştirildi
    slayt_gorev_dagilimi(prs, 5)
    slayt_calisma(prs, 6)
    slayt_proje(prs, 7)
    slayt_kanit(prs, 8)
    slayt_motivasyon(prs, 9)
    slayt_kapanis(prs, 10)

    cikti.parent.mkdir(parents=True, exist_ok=True)
    try:
        prs.save(str(cikti))
        return len(prs.slides._sldIdLst), cikti
    except PermissionError:
        yedek = cikti.with_name(cikti.stem + "_yeni.pptx")
        prs.save(str(yedek))
        return len(prs.slides._sldIdLst), yedek


def main() -> None:
    ap = argparse.ArgumentParser(description="AGENTRA TECH Takım Tanıtım Sunumu üreticisi")
    ap.add_argument("--cikti", type=Path,
                    default=PROJE_KOKU / "presentations" / "Agentra_Tech_Takim_Tanitim_Sunum.pptx")
    args = ap.parse_args()
    adet, yazilan = uret(args.cikti)
    if yazilan != args.cikti:
        print(f"UYARI: {args.cikti.name} acik/kilitli oldugu icin yedek ada yazildi.")
    print(f"Sunum uretildi: {yazilan} ({adet} slayt)")
    print("Hatirlatma: PDF surumunu PowerPoint'ten 'Farkli Kaydet -> PDF' ile alin.")


if __name__ == "__main__":
    main()
