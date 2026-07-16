#!/usr/bin/env python3
# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""AGENTRA TECH — Takım Tanıtım Sunumu üreticisi (kurumsal, kısıtlı palet).

TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (1. Senaryo) — Ön Değerlendirme
Formu için "takım tanıtım sunumu". Güncel şartname m.3.1'e göre bu aşama proje
sunumu DEĞİLDİR; amaç takımın organizasyon yapısını, ekip üyelerini ve görev
dağılımını tanıtmaktır. Tasarım olgun ve kurumsaldır: lacivert + çelik mavisi
iki tonluk kısıtlı palet, nötr griler, bol beyaz alan; renkli/çocuksu zeminler yok.

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
TOPLAM_SLAYT = 11


# ----------------------------------------------------------------------------
# Kısıtlı kurumsal palet — lacivert + çelik mavisi + nötrler
# ----------------------------------------------------------------------------
def C(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


NAVY = C("14263F")      # birincil koyu (kapak, koyu kutular, 2. ton)
NAVY2 = C("1C3350")
STEEL = C("2E5A87")     # tek vurgu rengi (çelik mavisi)
INK = C("1E2A3A")       # ana metin
MUTED = C("64728A")     # ikincil metin
LINE = C("D7DEEA")      # kart/çizgi kenarı
SOFT = C("F5F7FA")      # yumuşak nötr panel zemini
WHITE = C("FFFFFF")
RED = C("C8102E")       # yalnızca kapak/kapanış kenar şeridi + kaptan rozeti
GOLD = C("C9A24B")      # yalnızca koyu kutu başlığı (tek incelikli dokunuş)
ICONBG = C("EDF1F6")    # ikon dairesi nötr zemini

# Anlamsal adlar → iki tonluk palete indirgenir (renk çeşitliliği yok)
BLUE = STEEL
TEAL = STEEL
GREEN = STEEL
PURPLE = NAVY
ORANGE = NAVY
# Üyeler: çelik/lacivert dönüşümlü (çeşitlilik değil, hafif ayrım)
SEYMA = STEEL
SINA = NAVY
ZEYNEP = STEEL
EMINE = NAVY

BODY = "Segoe UI"; SEMI = "Segoe UI Semibold"; MONO = "Consolas"
W_IN, H_IN = 13.333, 7.5


# ----------------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------------
def R(text, color=INK, bold=False, size=14, font=BODY):
    return (text, color, bold, size, font)


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
        for (txt, color, bold, size, font) in pa["runs"]:
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(size); r.font.bold = bold
            r.font.color.rgb = color; r.font.name = font
    return tf


def _noshadow(sp):
    try:
        sp.shadow.inherit = False
    except Exception:
        pass


def rrect(slide, x, y, w, h, fill, line=None, line_w=1.0, radius=0.08):
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


def arrow(slide, x, y, w, h, color=C("B4BECD"), direction="right"):
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


def node(slide, x, y, w, h, title, sub=None, fill=WHITE, tcolor=INK,
         line=LINE, tsize=14, ssize=10.5, radius=0.1, bold=True):
    sp = rrect(slide, x, y, w, h, fill, line=line, line_w=1.25, radius=radius)
    paras = [P([R(title, tcolor, bold, tsize, SEMI)], align=PP_ALIGN.CENTER, space_after=1)]
    if sub:
        paras.append(P([R(sub, tcolor, False, ssize, BODY)], align=PP_ALIGN.CENTER, space_after=0))
    shape_text(sp, paras, anchor=MSO_ANCHOR.MIDDLE)
    return sp


def pill(slide, x, y, w, h, text, fill, tcolor=WHITE, size=11, bold=True):
    sp = rrect(slide, x, y, w, h, fill, line=None, radius=0.5)
    shape_text(sp, [P([R(text, tcolor, bold, size, SEMI)], align=PP_ALIGN.CENTER,
                      space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
    return sp


def kpi_tile(slide, x, y, w, h, big, unit, label, accent=STEEL):
    rrect(slide, x, y, w, h, WHITE, line=LINE, line_w=1.25, radius=0.06)
    rect(slide, x, y + 0.16, 0.09, h - 0.32, accent)
    runs = [R(big, accent, True, 34, SEMI)]
    if unit:
        runs.append(R(" " + unit, accent, True, 16, SEMI))
    textbox(slide, x + 0.3, y + 0.14, w - 0.38, 0.66, [P(runs)])
    textbox(slide, x + 0.32, y + h - 0.78, w - 0.44, 0.7,
            [P([R(label, INK, False, 12.5, BODY)], line=1.02)])


def card(slide, x, y, w, h, icon, title, body_lines, accent=STEEL):
    rrect(slide, x, y, w, h, WHITE, line=LINE, line_w=1.25, radius=0.06)
    rect(slide, x, y, w, 0.1, accent)
    textbox(slide, x + 0.28, y + 0.3, w - 0.44, 0.5,
            [P([R((icon + "  " if icon else ""), INK, True, 15, SEMI),
                R(title, INK, True, 15, SEMI)])])
    paras = [P([R("—  ", accent, True, 13, SEMI), R(t, INK, False, 13, BODY)],
               space_after=5, line=1.05) for t in body_lines]
    textbox(slide, x + 0.28, y + 0.9, w - 0.5, h - 1.02, paras)


def pipeline_strip(slide, y, items, x0=0.62, total_w=12.09, h=0.72):
    n = len(items)
    gap = 0.32
    sw = (total_w - gap * (n - 1)) / n
    x = x0
    for i, (t, col) in enumerate(items):
        node(slide, x, y, sw, h, t, fill=col, tcolor=WHITE, line=None, tsize=12.5, radius=0.12)
        x += sw
        if i < n - 1:
            arrow(slide, x + 0.02, y + h / 2 - 0.15, gap - 0.06, 0.3)
            x += gap


# ----------------------------------------------------------------------------
# Sayfa iskeleti
# ----------------------------------------------------------------------------
def new_slide(prs, dark=False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY if dark else WHITE
    return slide


def header(slide, kicker, title, accent=STEEL):
    textbox(slide, 0.62, 0.44, 12.1, 0.34, [P([R(kicker.upper(), accent, True, 12.5, SEMI)])])
    textbox(slide, 0.62, 0.76, 12.2, 0.8, [P([R(title, INK, True, 29, SEMI)])])


def footer(slide, n):
    rect(slide, 0.62, 7.06, 12.1, 0.014, LINE)
    textbox(slide, 0.62, 7.12, 8.6, 0.3,
            [P([R("AGENTRA TECH   ·   TEKNOFEST 2026 · Yapay Zeka Dil Ajanları Yarışması · 1. Senaryo",
                 MUTED, False, 9.5, BODY)])])
    textbox(slide, 11.3, 7.12, 1.42, 0.3,
            [P([R(f"{n:02d} / {TOPLAM_SLAYT:02d}", MUTED, False, 9.5, BODY)], align=PP_ALIGN.RIGHT)])


# ----------------------------------------------------------------------------
# 01 — Kapak
# ----------------------------------------------------------------------------
def slayt_kapak(prs):
    s = new_slide(prs, dark=True)
    rect(s, 0, 0, 0.16, H_IN, RED)
    rect(s, 0, H_IN - 0.14, W_IN, 0.14, NAVY2)
    net = [(11.0, 0.9), (12.2, 1.35), (11.7, 2.25), (12.6, 2.75), (10.6, 2.0)]
    import itertools
    for (a, b) in itertools.combinations(net, 2):
        conn = s.shapes.add_connector(1, Inches(a[0] + 0.11), Inches(a[1] + 0.11),
                                      Inches(b[0] + 0.11), Inches(b[1] + 0.11))
        conn.line.color.rgb = C("2C3F5C"); conn.line.width = Pt(0.75)
        _noshadow(conn)
    for (nx, ny) in net:
        oval(s, nx, ny, 0.2, 0.2, C("3A527A"))
    textbox(s, 0.9, 1.5, 9.2, 0.42,
            [P([R("TEKNOFEST 2026 · YAPAY ZEKA DİL AJANLARI YARIŞMASI", C("93A8CE"), True, 14, SEMI)])])
    textbox(s, 0.88, 1.98, 11.0, 1.2, [P([R("AGENTRA TECH", WHITE, True, 56, SEMI)])])
    textbox(s, 0.9, 3.42, 11.6, 1.1,
            [P([R("Takım Tanıtım Sunumu", WHITE, True, 26, SEMI)], space_after=4),
             P([R("Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi · 1. Senaryo",
                 C("C4CFE1"), False, 16.5, BODY)])])
    chips = ["4 Üye · 1 Kaptan", "Kuruluş 2026", "Açık Kaynak"]
    cx = 0.9
    for ch in chips:
        wch = 0.5 + len(ch) * 0.11
        pill(s, cx, 5.4, wch, 0.48, ch, NAVY2, tcolor=C("BFCCE2"), size=13)
        cx += wch + 0.24
    textbox(s, 0.9, 6.34, 11.0, 0.5,
            [P([R("Takım Kaptanı: Şeyma Nur Çebi", C("AEBDD8"), True, 14, SEMI),
                R("   ·   Temmuz 2026", C("7E8FAE"), False, 14, BODY)])])
    return s


# ----------------------------------------------------------------------------
# 02 — Kısaca Biz
# ----------------------------------------------------------------------------
def slayt_kunye(prs, n):
    s = new_slide(prs)
    header(s, "Takımımız", "Kısaca Biz")
    tiles = [
        ("4", "", "Takım üyesi", STEEL),
        ("1", "", "Takım kaptanı", NAVY),
        ("2026", "", "Kuruluş yılı", STEEL),
        ("3", "", "Farklı üniversite · 3 mühendislik dalı", NAVY),
        ("Açık", "", "Kaynak · Apache 2.0 · tamamı Türkçe", STEEL),
    ]
    x = 0.62; tw = 2.36
    for (big, unit, label, acc) in tiles:
        kpi_tile(s, x, 1.82, tw, 1.55, big, unit, label, acc)
        x += tw + 0.11
    rrect(s, 0.62, 3.62, 12.09, 1.28, SOFT, line=LINE, line_w=1.25, radius=0.05)
    rect(s, 0.62, 3.62, 0.1, 1.28, STEEL)
    textbox(s, 0.98, 3.78, 11.5, 1.02,
            [P([R("Biz ", INK, False, 15.5, BODY), R("AGENTRA TECH", INK, True, 16, SEMI),
                R("; TEKNOFEST 2026 için bir araya gelen, ", INK, False, 15.5, BODY),
                R("Türkçe dil teknolojileri ve akıllı ajan sistemleri", STEEL, True, 15.5, SEMI),
                R(" üzerine çalışan 4 kişilik bir öğrenci takımıyız.", INK, False, 15.5, BODY)], line=1.14),
             P([R("Adımızın merkezinde “agent” var: kararları izlenebilir, tamamen açık kaynak bir sistem geliştiriyoruz.",
                 MUTED, False, 13, BODY)], space_before=4)])
    members = [("Şeyma Nur Çebi", SEYMA), ("Muhammed Sina Gün", SINA),
               ("Emine Elik", EMINE), ("Zeynep Akel", ZEYNEP)]
    x = 0.62
    for (nm, col) in members:
        w = 0.72 + len(nm) * 0.122
        rrect(s, x, 5.26, w, 0.66, WHITE, line=LINE, line_w=1.25, radius=0.3)
        oval(s, x + 0.18, 5.43, 0.32, 0.32, col)
        shape_text(s.shapes[-1], [P([R(nm[0], WHITE, True, 12.5, SEMI)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 0.6, 5.42, w - 0.62, 0.38, [P([R(nm, INK, True, 13, SEMI)])])
        x += w + 0.22
    textbox(s, 0.62, 6.3, 12.0, 0.4,
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
    rrect(s, 0.62, 1.78, 6.35, 4.62, SOFT, line=LINE, line_w=1.25, radius=0.05)
    rect(s, 0.62, 1.78, 0.1, 4.62, STEEL)
    textbox(s, 0.98, 1.98, 5.85, 0.45, [P([R("Kuruluş & Amaç", INK, True, 18, SEMI)])])
    textbox(s, 0.98, 2.6, 5.9, 3.7,
            [P([R("Kuruluş: ", STEEL, True, 14, SEMI), R("2026", INK, True, 14, SEMI),
                R("   ·   4 kişilik öğrenci takımı", INK, False, 13, BODY)], space_after=10),
             P([R("Takım adı: ", STEEL, True, 14, SEMI),
                R("AGENTRA TECH — merkezinde “agent” (ajan) odağı vardır.",
                  INK, False, 13.5, BODY)], space_after=10, line=1.12),
             P([R("Amacımız", STEEL, True, 14, SEMI)], space_after=4),
             P([R("Kamu evrak ve yazışma süreçlerini okuyan, anlayan, eksiğini bulan, mevzuat öneren, "
                  "resmî yazı taslaklayıp doğru birime yönlendiren; çok ajanlı, offline-first ve yerli "
                  "bir yapay zekâ sistemiyle uçtan uca otomatikleştirmek.",
                  INK, False, 13.5, BODY)], line=1.18)])
    textbox(s, 7.2, 1.92, 5.5, 0.45, [P([R("Değerlerimiz", INK, True, 18, SEMI)])])
    vals = [
        ("Güvenilirlik", "Her karar bir güven skoruyla gelir."),
        ("Şeffaflık", "Her öneri gerekçe ve madde dayanağı taşır."),
        ("Veri Koruması (KVKK)", "Kişisel veri sızdırılmaz; yerli ve offline."),
        ("Dürüstlük", "Ölçümler ne çıkarsa olduğu gibi raporlanır."),
    ]
    y = 2.57
    for (tt, bd) in vals:
        rrect(s, 7.2, y, 5.5, 0.92, WHITE, line=LINE, line_w=1.25, radius=0.08)
        rect(s, 7.2, y, 0.1, 0.92, STEEL)
        textbox(s, 7.44, y + 0.14, 5.1, 0.4, [P([R(tt, INK, True, 14.5, SEMI)])])
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
    rrect(s, tx, 1.74, tw, 0.9, NAVY, line=None, radius=0.08)
    shape_text(s.shapes[-1],
               [P([R("AGENTRA TECH", WHITE, True, 18, SEMI)], align=PP_ALIGN.CENTER, space_after=1),
                P([R("4 kişilik takım · Kuruluş 2026", C("AEBDD8"), False, 12, BODY)],
                  align=PP_ALIGN.CENTER, space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
    people = [
        ("Ş", "Şeyma Nur Çebi", "İçerik Analizi &\nDeğerlendirme", SEYMA, True),
        ("M", "Muhammed Sina Gün", "Mimari &\nOrkestrasyon", SINA, False),
        ("Z", "Zeynep Akel", "Etkileşim · Yönlendirme\n· KVKK", ZEYNEP, False),
        ("E", "Emine Elik", "Veri · Test ·\nDoküman · Sunum", EMINE, False),
    ]
    bw = 2.86; gap = (12.09 - 4 * bw) / 3
    xs = [0.62 + i * (bw + gap) for i in range(4)]
    centers = [x + bw / 2 for x in xs]
    top_cx = tx + tw / 2
    bus_y = 3.24
    box_y = 3.7
    lineseg = lambda x, y, w, h: rect(s, x, y, w, h, C("B4BECD"))
    lineseg(top_cx - 0.012, 2.64, 0.024, bus_y - 2.64)
    lineseg(min(centers) - 0.012, bus_y, (max(centers) - min(centers)) + 0.024, 0.024)
    for cx in centers:
        lineseg(cx - 0.012, bus_y, 0.024, box_y - bus_y)
    bh = 2.12
    for (ini, nm, fn, col, cap), x in zip(people, xs):
        rrect(s, x, box_y, bw, bh, WHITE, line=LINE, line_w=1.25, radius=0.06)
        rect(s, x, box_y, bw, 0.1, col)
        oval(s, x + bw / 2 - 0.36, box_y + 0.22, 0.72, 0.72, col)
        shape_text(s.shapes[-1], [P([R(ini, WHITE, True, 24, SEMI)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 0.1, box_y + 1.04, bw - 0.2, 0.4,
                [P([R(nm, INK, True, 14, SEMI)], align=PP_ALIGN.CENTER, line=0.98)])
        paras = [P([R(seg, MUTED, False, 12, BODY)], align=PP_ALIGN.CENTER, space_after=0, line=1.02)
                 for seg in fn.split("\n")]
        textbox(s, x + 0.08, box_y + 1.48, bw - 0.16, 0.62, paras)
        if cap:
            pill(s, x + bw / 2 - 0.72, box_y - 0.18, 1.44, 0.36, "★ TAKIM KAPTANI", RED, size=10)
    rrect(s, 0.62, 6.14, 12.09, 0.74, SOFT, line=LINE, line_w=1.25, radius=0.06)
    textbox(s, 0.98, 6.28, 11.5, 0.5,
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
    header(s, "Ekip Üyeleri", "Takım Üyeleri ve Sorumlulukları")
    members = [
        ("Şeyma Nur Çebi", "TAKIM KAPTANI · YAZILIM", SEYMA, "Yazılım Müh. · 3. Sınıf · Arel Üni.",
         "Görev 1 içerik analizi: sınıflandırma, bilgi çıkarımı, mevzuat RAG; değerlendirme ve entegrasyon.", True),
        ("Muhammed Sina Gün", "YAZILIM", SINA, "Bilgisayar Müh. · 3. Sınıf · Arel Üni.",
         "Mimari ve orkestrasyon; model-agnostik LLM katmanı; Görev 2 taslak üretimi (OCR, özet).", False),
        ("Emine Elik", "VERİ · TEST · DOKÜMAN", EMINE, "Maden Müh. · 1. Sınıf · Cerrahpaşa Üni.",
         "Veri seti ve etiketleme; test kapsamı; dokümantasyon; sunum ve demo; şartname uyumu.", False),
        ("Zeynep Akel", "YAZILIM", ZEYNEP, "Yazılım Müh. · 3. Sınıf · Biruni Üni.",
         "Görev 1 eksik bilgi; Görev 2 yönlendirme ve kullanıcı etkileşimi; triyaj, KVKK; web arayüzü.", False),
    ]
    pos = [(0.62, 1.66), (6.72, 1.66), (0.62, 4.14), (6.72, 4.14)]
    cw, ch = 6.0, 2.36
    for (name, role, col, akademik, desc, cap), (x, y) in zip(members, pos):
        rrect(s, x, y, cw, ch, WHITE, line=LINE, line_w=1.25, radius=0.06)
        rect(s, x, y, 0.13, ch, col)
        oval(s, x + 0.3, y + 0.36, 0.88, 0.88, col)
        shape_text(s.shapes[-1], [P([R(name[0], WHITE, True, 27, SEMI)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 1.42, y + 0.3, cw - 1.6, 0.42, [P([R(name, INK, True, 17.5, SEMI)])])
        textbox(s, x + 1.44, y + 0.82, cw - 1.6, 0.34, [P([R(akademik, STEEL, True, 12, SEMI)])])
        pill(s, x + 1.44, y + 1.2, min(cw - 1.6, 0.6 + len(role) * 0.1), 0.34, role, col, size=11)
        textbox(s, x + 0.34, y + 1.68, cw - 0.62, 0.62,
                [P([R(desc, MUTED, False, 12.5, BODY)], line=1.06)])
        if cap:
            pill(s, x + cw - 1.5, y + 0.26, 1.3, 0.36, "★ KAPTAN", RED, size=10.5)
    textbox(s, 0.62, 6.56, 12.1, 0.4,
            [P([R("4 üye · 3 üniversite · Yazılım, Bilgisayar ve Maden Mühendisliği öğrencileri.",
                 MUTED, False, 12.5, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 06 — Görev Dağılımı
# ----------------------------------------------------------------------------
def slayt_gorev_dagilimi(prs, n):
    s = new_slide(prs)
    header(s, "Görev Dağılımı", "Görev Dağılımımız · Şartname m.6.4")
    person_col = {"Şeyma Nur": SEYMA, "Sina": SINA, "Zeynep": ZEYNEP, "Emine": EMINE}

    def panel(x, w, title, acc, rows):
        rrect(s, x, 1.68, w, 4.12, WHITE, line=LINE, line_w=1.25, radius=0.05)
        rrect(s, x, 1.68, w, 0.56, acc, line=None, radius=0.05)
        rect(s, x, 2.06, w, 0.16, acc)
        textbox(s, x, 1.7, w, 0.5, [P([R(title, WHITE, True, 13.5, SEMI)],
                align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
        ry = 2.38
        for j, (cap, who) in enumerate(rows):
            if j % 2 == 1:
                rect(s, x + 0.12, ry, w - 0.24, 0.55, SOFT)
            textbox(s, x + 0.3, ry + 0.14, w - 2.0, 0.34, [P([R(cap, INK, False, 13, BODY)])])
            pw = 0.44 + len(who) * 0.105
            pill(s, x + w - pw - 0.28, ry + 0.11, pw, 0.34, who, person_col[who], size=10.5)
            ry += 0.565

    panel(0.62, 6.0, "GÖREV 1 — Sınıflandırma & İçerik Analizi", STEEL, [
        ("OCR / metin okuma", "Sina"),
        ("Tür belirleme (sınıflandırma)", "Şeyma Nur"),
        ("Bilgi çıkarımı", "Şeyma Nur"),
        ("Eksik bilgi tespiti", "Zeynep"),
        ("Mevzuat önerisi (BM25 RAG)", "Şeyma Nur"),
        ("Özet oluşturma", "Sina"),
    ])
    panel(6.72, 6.0, "GÖREV 2 — Taslaklama & Yönlendirme", NAVY, [
        ("Resmî yazı taslağı", "Sina"),
        ("Format öz-denetimi (üslup)", "Sina"),
        ("Birim yönlendirme", "Zeynep"),
        ("Kullanıcı bilgilendirme", "Zeynep"),
        ("Eksik bilgi talebi", "Zeynep"),
        ("Altyapı: veri · test · doküman", "Emine"),
    ])
    textbox(s, 0.62, 5.94, 6.0, 0.4,
            [P([R("Her yetenek bir sorumluya ve gerçek bir kod modülüne bağlıdır.",
                 MUTED, False, 12, BODY)])])
    lx = 7.35
    textbox(s, 6.72, 5.92, 0.6, 0.34, [P([R("Ekip:", MUTED, True, 11.5, SEMI)])])
    for name, col in person_col.items():
        w = 0.4 + len(name) * 0.1
        pill(s, lx, 5.9, w, 0.34, name, col, size=10)
        lx += w + 0.14
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 07 — Nasıl Çalışıyoruz
# ----------------------------------------------------------------------------
def slayt_calisma(prs, n):
    s = new_slide(prs)
    header(s, "Çalışma Biçimimiz", "Nasıl Çalışıyoruz?")
    pipeline_strip(s, 1.98, [
        ("Fikir", C("3A527A")), ("Geliştirme", NAVY), ("Test & Ölçüm", STEEL),
        ("Dürüst Rapor", C("3A527A")), ("İyileştirme", NAVY),
    ], h=0.78)
    textbox(s, 0.62, 2.92, 12.0, 0.4,
            [P([R("Her özellik; fikirden koda, otomatik testlere ve dürüst ölçüme kadar aynı döngüden geçer.",
                 MUTED, False, 12.5, BODY)], align=PP_ALIGN.CENTER)])
    cards = [
        (None, "Açık ve İzlenebilir", ["Ortak GitHub deposu (Apache 2.0)",
         "Her karar kayıt altında", "Tüm dokümantasyon Türkçe"], STEEL),
        (None, "Sürekli Entegrasyon", ["En az haftalık commit",
         "500+ otomatik test yeşil", "Her katkı gözden geçirilir"], NAVY),
        (None, "Dürüst Ölçüm", ["Düzenli değerlendirme ölçümü",
         "Tutulmuş (held-out) setler", "Sonuçlar olduğu gibi raporlanır"], STEEL),
    ]
    x = 0.62; cw = 3.93
    for (ic, tt, bl, ac) in cards:
        card(s, x, 3.52, cw, 3.0, ic, tt, bl, ac)
        x += cw + 0.14
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 08 — Projemiz (kısa)
# ----------------------------------------------------------------------------
def slayt_proje(prs, n):
    s = new_slide(prs)
    header(s, "Kısa Proje Tanıtımı", "Ne Geliştiriyoruz?")
    rrect(s, 0.62, 1.74, 12.09, 1.16, SOFT, line=LINE, line_w=1.25, radius=0.05)
    rect(s, 0.62, 1.74, 0.1, 1.16, STEEL)
    textbox(s, 0.98, 1.88, 11.5, 0.95,
            [P([R("Kamu kurumlarına gelen evrağı ", INK, False, 15.5, BODY),
                R("okuyan · anlayan · eksiğini bulan · mevzuat öneren · taslaklayan · yönlendiren",
                  STEEL, True, 15.5, SEMI),
                R(" çok ajanlı bir yapay zekâ sistemi.", INK, False, 15.5, BODY)], line=1.12),
             P([R("11 uzman ajan + orkestratör · framework bağımsız saf Python · çevrimdışı-öncelikli",
                 MUTED, False, 12.5, BODY)], space_before=4)])
    pipeline_strip(s, 3.2, [
        ("Girdi", C("3A527A")), ("Orkestratör", NAVY), ("Görev 1", STEEL),
        ("Görev 2", NAVY), ("12+ Çıktı", STEEL),
    ], h=0.76)
    card(s, 0.62, 4.26, 5.95, 2.1, None, "Görev 1 — Sınıflandırma & İçerik",
         ["Metin/PDF/görüntü okuma (OCR) + tür belirleme",
          "Bilgi çıkarımı · eksik bilgi tespiti",
          "Mevzuat önerisi · kısa özet"], STEEL)
    card(s, 6.76, 4.26, 5.95, 2.1, None, "Görev 2 — Taslaklama & Yönlendirme",
         ["Resmî yazı taslağı (Yönetmelik uyumlu)",
          "Gerekçeli birim yönlendirme",
          "Kullanıcı bilgilendirme · eksik bilgi talebi"], NAVY)
    textbox(s, 0.62, 6.54, 12.1, 0.4,
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
        ("✓", "", "Çalışan sistem · CLI + web arayüzü + demo", STEEL),
        ("500", "+", "Test — sürekli entegrasyonda yeşil", NAVY),
        ("116", "", "Etiketli sentetik kurgu evrak", STEEL),
        ("0", "", "KVKK sızıntısı (bağımsız denetim)", NAVY),
    ]
    x = 0.62; tw = 2.97
    for (big, unit, label, acc) in tiles:
        kpi_tile(s, x, 1.82, tw, 1.55, big, unit, label, acc)
        x += tw + 0.12

    def olcum(x, w, title, acc, rows):
        rrect(s, x, 3.62, w, 2.16, WHITE, line=LINE, line_w=1.25, radius=0.05)
        rect(s, x, 3.62, w, 0.12, acc)
        textbox(s, x + 0.26, 3.84, w - 0.42, 0.4, [P([R(title, INK, True, 14, SEMI)])])
        paras = [P([R(lbl + "   ", INK, False, 13, BODY), R(val, acc, True, 13, SEMI)],
                   space_after=6) for (lbl, val) in rows]
        textbox(s, x + 0.26, 4.36, w - 0.46, 1.4, paras)

    olcum(0.62, 5.95, "Geliştirme seti · 52 evrak", STEEL, [
        ("Sınıflandırma doğruluğu", "1,00"), ("Birim yönlendirme", "0,96"),
        ("Eksik-bilgi tespiti (F1)", "1,00"), ("Mevzuat isabet@3", "0,96"),
    ])
    olcum(6.77, 5.95, "Adversarial tutulmuş set · 16 evrak", NAVY, [
        ("Sınıflandırma doğruluğu", "0,94"), ("Birim yönlendirme", "1,00"),
        ("Eksik-bilgi tespiti (F1)", "0,83"), ("Mevzuat isabet@3", "0,94"),
    ])
    textbox(s, 0.62, 5.94, 12.1, 0.4,
            [P([R("Kaynak: ", MUTED, True, 11.5, SEMI),
                R("eval_report*.json", INK, False, 11.5, MONO),
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
    pos = [(0.62, 1.78), (4.66, 1.78), (8.7, 1.78), (0.62, 4.04), (4.66, 4.04)]
    cw, ch = 3.9, 2.08
    for (tt, bd), (x, y) in zip(items, pos):
        rrect(s, x, y, cw, ch, WHITE, line=LINE, line_w=1.25, radius=0.06)
        rect(s, x, y, cw, 0.1, STEEL)
        textbox(s, x + 0.3, y + 0.34, cw - 0.5, 0.6, [P([R(tt, INK, True, 15, SEMI)], line=1.0)])
        textbox(s, x + 0.3, y + 1.02, cw - 0.54, 0.95, [P([R(bd, MUTED, False, 12.5, BODY)], line=1.1)])
    rrect(s, 8.7, 4.04, 3.9, 2.08, NAVY, line=None, radius=0.06)
    textbox(s, 8.98, 4.26, 3.42, 1.75,
            [P([R("Kamuya uygun yapay zekâ", GOLD, True, 15.5, SEMI)], space_after=5),
             P([R("“Her şeyi otomatikleştiren” değil; ", C("D8E2F3"), False, 13, BODY),
                R("doğru yerde insana devreden", WHITE, True, 13, SEMI),
                R(" bir sistem güven verir.", C("D8E2F3"), False, 13, BODY)], line=1.12)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 11 — Kapanış
# ----------------------------------------------------------------------------
def slayt_kapanis(prs, n):
    s = new_slide(prs, dark=True)
    rect(s, 0, 0, 0.16, H_IN, RED)
    net = [(11.0, 0.85), (12.3, 1.3), (11.6, 2.2), (12.5, 2.7)]
    import itertools
    for (a, b) in itertools.combinations(net, 2):
        conn = s.shapes.add_connector(1, Inches(a[0] + 0.1), Inches(a[1] + 0.1),
                                      Inches(b[0] + 0.1), Inches(b[1] + 0.1))
        conn.line.color.rgb = C("2C3F5C"); conn.line.width = Pt(0.75)
        _noshadow(conn)
    for (nx, ny) in net:
        oval(s, nx, ny, 0.2, 0.2, C("3A527A"))
    textbox(s, 0.9, 1.1, 11.0, 0.4, [P([R("TEŞEKKÜRLER", C("93A8CE"), True, 15, SEMI)])])
    textbox(s, 0.88, 1.5, 11.2, 1.0, [P([R("AGENTRA TECH", WHITE, True, 48, SEMI)])])
    textbox(s, 0.9, 2.68, 11.6, 0.5,
            [P([R("Organizasyon yapısı, ekip ve görev dağılımıyla; kamuya uygun bir yapay zekâ takımı.",
                 C("C4CFE1"), False, 15.5, BODY)])])
    members = [("Şeyma Nur Çebi", "Kaptan", SEYMA), ("Muhammed Sina Gün", "", SINA),
               ("Emine Elik", "", EMINE), ("Zeynep Akel", "", ZEYNEP)]
    x = 0.9
    for (nm, rl, col) in members:
        w = 0.62 + len(nm) * 0.125 + (len(rl) * 0.095 if rl else 0)
        rrect(s, x, 3.56, w, 0.62, NAVY2, line=None, radius=0.3)
        oval(s, x + 0.18, 3.72, 0.3, 0.3, col)
        runs = [R(nm, WHITE, True, 13, SEMI)]
        if rl:
            runs.append(R("  · " + rl, C("9FB0CE"), False, 11, BODY))
        textbox(s, x + 0.58, 3.65, w - 0.58, 0.4, [P(runs)])
        x += w + 0.22
    rrect(s, 0.9, 4.62, 9.6, 0.8, NAVY2, line=None, radius=0.08)
    textbox(s, 1.2, 4.8, 9.2, 0.44,
            [P([R("Depo:  ", C("9FB0CE"), True, 14, SEMI),
                R("github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan", WHITE, False, 14, MONO)])])
    textbox(s, 0.9, 5.88, 11.6, 0.6,
            [P([R("Kamuya uygun, dürüst, açık kaynak ve ", C("C4CFE1"), False, 15.5, BODY),
                R("bugün çalışan", WHITE, True, 15.5, SEMI),
                R(" bir sistem geliştiren bir takımız.", C("C4CFE1"), False, 15.5, BODY)])])
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
    slayt_organizasyon(prs, 4)
    slayt_uyeler(prs, 5)
    slayt_gorev_dagilimi(prs, 6)
    slayt_calisma(prs, 7)
    slayt_proje(prs, 8)
    slayt_kanit(prs, 9)
    slayt_motivasyon(prs, 10)
    slayt_kapanis(prs, 11)

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
