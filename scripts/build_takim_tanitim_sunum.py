#!/usr/bin/env python3
# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""AGENTRA TECH — Takım Tanıtım Sunumu üreticisi (görsel/diyagramlı, takım odaklı).

TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (1. Senaryo) — Ön Değerlendirme
Formu için "takım tanıtım sunumu". Güncel şartname m.3.1'e göre bu aşama bir PROJE
SUNUMU DEĞİLDİR; amaç takımın "organizasyon yapısını, ekip üyelerini ve görev
dağılımlarını" tanıtmaktır. Bu yüzden sunum takım-önceliklidir: organizasyon şeması,
üye kartları, görev dağılımı matrisi ve çalışma biçimi öne çıkar; proje yalnızca kısa,
destekleyici bir özetle yer alır (teknik derinlik finale bırakılır).

Kullanım:
    pip install -r requirements-optional.txt   # python-pptx (yalnızca ilk sefer)
    python scripts/build_takim_tanitim_sunum.py
    # PDF sürümü: PowerPoint'te açıp Dosya -> Farklı Kaydet -> PDF

Dürüstlük: takım/rol bilgileri AUTHORS + takım tanıtım dosyası; metrikler
data/processed/eval_report*.json.
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
# Tasarım sistemi
# ----------------------------------------------------------------------------
def C(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


NAVY = C("0E1B33"); NAVY2 = C("16264A")
INK = C("1A2233"); MUTED = C("5B6B85"); LINE = C("DCE3EF")
WHITE = C("FFFFFF"); SOFT = C("F3F6FB")
RED = C("C8102E"); BLUE = C("1B6FC2"); ORANGE = C("E8590C")
PURPLE = C("6C3FD1"); TEAL = C("0CA678"); GREEN = C("2F9E44"); GOLD = C("F1B434")

SEYMA = C("1B6FC2"); SINA = C("6C3FD1"); ZEYNEP = C("0CA678"); EMINE = C("E8590C")

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


def rrect(slide, x, y, w, h, fill, line=None, line_w=1.0, radius=0.09):
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


def arrow(slide, x, y, w, h, color=C("AEB9CE"), direction="right"):
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
         line=LINE, tsize=12.5, ssize=9, radius=0.12, bold=True):
    sp = rrect(slide, x, y, w, h, fill, line=line, line_w=1.25, radius=radius)
    paras = [P([R(title, tcolor, bold, tsize, SEMI)], align=PP_ALIGN.CENTER, space_after=1)]
    if sub:
        paras.append(P([R(sub, tcolor, False, ssize, BODY)], align=PP_ALIGN.CENTER, space_after=0))
    shape_text(sp, paras, anchor=MSO_ANCHOR.MIDDLE)
    return sp


def pill(slide, x, y, w, h, text, fill, tcolor=WHITE, size=9.5, bold=True):
    sp = rrect(slide, x, y, w, h, fill, line=None, radius=0.5)
    shape_text(sp, [P([R(text, tcolor, bold, size, SEMI)], align=PP_ALIGN.CENTER,
                      space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
    return sp


def kpi_tile(slide, x, y, w, h, big, unit, label, accent=BLUE):
    rrect(slide, x, y, w, h, WHITE, line=LINE, line_w=1.25, radius=0.1)
    rect(slide, x, y + 0.14, 0.07, h - 0.28, accent)
    runs = [R(big, accent, True, 29, SEMI)]
    if unit:
        runs.append(R(" " + unit, accent, True, 13, SEMI))
    textbox(slide, x + 0.22, y + 0.16, w - 0.3, 0.6, [P(runs)])
    textbox(slide, x + 0.24, y + h - 0.74, w - 0.36, 0.66,
            [P([R(label, INK, False, 10.5, BODY)], line=1.0)])


def card(slide, x, y, w, h, icon, title, body_lines, accent=BLUE):
    rrect(slide, x, y, w, h, WHITE, line=LINE, line_w=1.25, radius=0.09)
    rect(slide, x, y, w, 0.09, accent)
    textbox(slide, x + 0.22, y + 0.24, w - 0.4, 0.5,
            [P([R((icon + "  " if icon else ""), INK, True, 13, SEMI),
                R(title, INK, True, 13.5, SEMI)])])
    paras = [P([R("•  ", accent, True, 10.5, BODY), R(t, INK, False, 10.5, BODY)],
               space_after=3, line=1.02) for t in body_lines]
    textbox(slide, x + 0.22, y + 0.74, w - 0.42, h - 0.9, paras)


def lineseg(slide, x, y, w, h, color=C("AEB9CE")):
    """İnce bağlantı çizgisi (organizasyon şeması için)."""
    rect(slide, x, y, w, h, color)


def pipeline_strip(slide, y, items, x0=0.62, total_w=12.09, h=0.66):
    n = len(items)
    gap = 0.32
    sw = (total_w - gap * (n - 1)) / n
    x = x0
    for i, (t, col) in enumerate(items):
        node(slide, x, y, sw, h, t, fill=col, tcolor=WHITE, line=None, tsize=11.5, radius=0.16)
        x += sw
        if i < n - 1:
            arrow(slide, x + 0.02, y + h / 2 - 0.15, gap - 0.06, 0.3, C("B7C1D4"))
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


def header(slide, kicker, title, accent=RED):
    textbox(slide, 0.62, 0.40, 12.1, 0.32, [P([R(kicker.upper(), accent, True, 11, SEMI)])])
    textbox(slide, 0.58, 0.66, 12.2, 0.7, [P([R(title, INK, True, 25, SEMI)])])
    rect(slide, 0.64, 1.42, 0.9, 0.055, accent)


def footer(slide, n):
    rect(slide, 0.62, 7.02, 12.1, 0.014, LINE)
    textbox(slide, 0.62, 7.08, 8.4, 0.3,
            [P([R("AGENTRA TECH  ·  TEKNOFEST 2026 · Yapay Zeka Dil Ajanları Yarışması · 1. Senaryo",
                 MUTED, False, 8.5, BODY)])])
    textbox(slide, 11.3, 7.08, 1.42, 0.3,
            [P([R(f"{n:02d} / {TOPLAM_SLAYT:02d}", MUTED, False, 8.5, BODY)], align=PP_ALIGN.RIGHT)])


# ----------------------------------------------------------------------------
# 01 — Kapak
# ----------------------------------------------------------------------------
def slayt_kapak(prs):
    s = new_slide(prs, dark=True)
    rect(s, 0, 0, 0.16, H_IN, RED)
    rect(s, 0, H_IN - 0.16, W_IN, 0.16, NAVY2)
    net = [(11.0, 0.9), (12.2, 1.35), (11.7, 2.25), (12.6, 2.75), (10.6, 2.0)]
    import itertools
    for (a, b) in itertools.combinations(net, 2):
        conn = s.shapes.add_connector(1, Inches(a[0] + 0.11), Inches(a[1] + 0.11),
                                      Inches(b[0] + 0.11), Inches(b[1] + 0.11))
        conn.line.color.rgb = C("2A3E63"); conn.line.width = Pt(0.75)
        _noshadow(conn)
    for (nx, ny) in net:
        oval(s, nx, ny, 0.22, 0.22, C("35507F"))
    textbox(s, 0.9, 1.55, 8.5, 0.4,
            [P([R("TEKNOFEST 2026 · YAPAY ZEKA DİL AJANLARI YARIŞMASI", C("8FB0E8"), True, 12.5, SEMI)])])
    textbox(s, 0.88, 2.0, 11.0, 1.2, [P([R("AGENTRA TECH", WHITE, True, 54, SEMI)])])
    rect(s, 0.94, 3.18, 3.2, 0.05, RED)
    textbox(s, 0.9, 3.42, 11.4, 1.0,
            [P([R("Takım Tanıtım Sunumu", WHITE, True, 24, SEMI)], space_after=2),
             P([R("Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi · 1. Senaryo",
                 C("D5DEEF"), False, 15, BODY)])])
    chips = ["4 Üye · 1 Kaptan", "Kuruluş 2026", "Açık Kaynak"]
    cx = 0.9
    for ch in chips:
        wch = 0.42 + len(ch) * 0.1
        pill(s, cx, 5.35, wch, 0.42, ch, NAVY2, tcolor=C("BFD0EC"), size=11)
        cx += wch + 0.22
    textbox(s, 0.9, 6.28, 11.0, 0.5,
            [P([R("Takım Kaptanı: Şeyma Nur Çebi", C("AEC2E6"), True, 12.5, SEMI),
                R("   ·   Temmuz 2026", C("8296B6"), False, 12.5, BODY)])])
    return s


# ----------------------------------------------------------------------------
# 02 — Takım Künyesi (Bir Bakışta)
# ----------------------------------------------------------------------------
def slayt_kunye(prs, n):
    s = new_slide(prs)
    header(s, "Bir Bakışta", "Takım Künyemiz")
    tiles = [
        ("4", "", "Takım üyesi", SEYMA),
        ("1", "", "Takım kaptanı", RED),
        ("2026", "", "Kuruluş yılı", PURPLE),
        ("4", "", "Uzmanlık alanı: yazılım · veri · test · doküman", ORANGE),
        ("Apache", "2.0", "Açık kaynak · tamamı Türkçe", GREEN),
    ]
    x = 0.62; tw = 2.36
    for (big, unit, label, acc) in tiles:
        kpi_tile(s, x, 1.75, tw, 1.55, big, unit, label, acc)
        x += tw + 0.11
    rrect(s, 0.62, 3.6, 12.09, 1.2, SOFT, line=LINE, line_w=1.0, radius=0.06)
    rect(s, 0.62, 3.6, 0.09, 1.2, RED)
    textbox(s, 0.95, 3.76, 11.5, 0.95,
            [P([R("AGENTRA TECH", INK, True, 14.5, SEMI),
                R(" — TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması 1. Senaryo için kurulmuş, ",
                  INK, False, 14, BODY),
                R("Türkçe dil teknolojileri ve akıllı ajan sistemlerine", INK, True, 14, SEMI),
                R(" odaklı 4 kişilik öğrenci takımı.", INK, False, 14, BODY)], line=1.12),
             P([R("Kimliğimizin merkezinde “agent” odağı vardır: her kararı izlenebilir, tamamen açık kaynak bir çözüm.",
                 MUTED, False, 12, BODY)], space_before=3)])
    # üye şeridi
    members = [("Şeyma Nur Çebi", SEYMA), ("Muhammed Sina Gün", SINA),
               ("Emine Elik", EMINE), ("Zeynep Akel", ZEYNEP)]
    x = 0.62
    for (nm, col) in members:
        w = 0.62 + len(nm) * 0.108
        rrect(s, x, 5.2, w, 0.62, WHITE, line=LINE, line_w=1.25, radius=0.3)
        oval(s, x + 0.16, 5.36, 0.3, 0.3, col)
        shape_text(s.shapes[-1], [P([R(nm[0], WHITE, True, 12, SEMI)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 0.56, 5.34, w - 0.6, 0.35, [P([R(nm, INK, True, 11.5, SEMI)])])
        x += w + 0.2
    textbox(s, 0.62, 6.15, 12.0, 0.4,
            [P([R("Şartname m.3.1: bu sunum takımın organizasyon yapısını, ekip üyelerini ve görev dağılımını tanıtır.",
                 MUTED, False, 10.5, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 03 — Kuruluş, Amaç & Değerler
# ----------------------------------------------------------------------------
def slayt_kimlik(prs, n):
    s = new_slide(prs)
    header(s, "Kimliğimiz", "Kuruluşumuz, Amacımız ve Değerlerimiz")
    # sol: kuruluş + amaç
    rrect(s, 0.62, 1.75, 6.35, 4.55, SOFT, line=LINE, line_w=1.0, radius=0.05)
    rect(s, 0.62, 1.75, 0.09, 4.55, PURPLE)
    textbox(s, 0.95, 1.95, 5.85, 0.4, [P([R("Kuruluş & Amaç", INK, True, 15, SEMI)])])
    textbox(s, 0.95, 2.5, 5.85, 3.6,
            [P([R("Kuruluş: ", PURPLE, True, 12.5, SEMI), R("2026", INK, True, 12.5, SEMI)],
               space_after=8),
             P([R("Takım adı: ", PURPLE, True, 12.5, SEMI),
                R("AGENTRA TECH — kimliğimizin merkezinde “agent” (ajan) odağı vardır.",
                  INK, False, 12, BODY)], space_after=8, line=1.1),
             P([R("Amacımız", PURPLE, True, 12.5, SEMI)], space_after=3),
             P([R("Kamu kurumlarındaki evrak ve yazışma süreçlerini okuyan, anlayan, eksiğini bulan, "
                  "mevzuat öneren, resmî yazı taslaklayıp doğru birime yönlendiren çok ajanlı, "
                  "offline-first ve yerli bir yapay zekâ sistemiyle uçtan uca otomatikleştirmek.",
                  INK, False, 12, BODY)], line=1.14)])
    # sağ: değerler
    textbox(s, 7.2, 1.85, 5.5, 0.4, [P([R("Değerlerimiz", INK, True, 15, SEMI)])])
    vals = [
        ("🛡️", "Güvenilirlik", "Her karar bir güven skoruyla gelir.", BLUE),
        ("🔍", "Şeffaflık", "Her öneri gerekçe ve madde dayanağı taşır.", PURPLE),
        ("🔒", "Veri Koruması (KVKK)", "Kişisel veri sızdırılmaz; yerli ve offline.", TEAL),
        ("🎯", "Dürüstlük", "Ölçümler ne çıkarsa olduğu gibi raporlanır.", RED),
    ]
    y = 2.4
    for (ic, tt, bd, ac) in vals:
        rrect(s, 7.2, y, 5.5, 0.88, WHITE, line=LINE, line_w=1.25, radius=0.1)
        rect(s, 7.2, y, 0.09, 0.88, ac)
        oval(s, 7.42, y + 0.22, 0.44, 0.44, C("EEF3FB"))
        shape_text(s.shapes[-1], [P([R(ic, INK, False, 15, BODY)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, 8.05, y + 0.13, 4.5, 0.35, [P([R(tt, INK, True, 12.5, SEMI)])])
        textbox(s, 8.05, y + 0.47, 4.55, 0.35, [P([R(bd, C("34405A"), False, 10.3, BODY)])])
        y += 0.98
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 04 — Organizasyon Yapısı (org chart)
# ----------------------------------------------------------------------------
def slayt_organizasyon(prs, n):
    s = new_slide(prs)
    header(s, "Organizasyon Yapısı", "Takımı Nasıl Örgütledik?")
    # tepe kutu
    tw = 5.4
    tx = (W_IN - tw) / 2
    rrect(s, tx, 1.72, tw, 0.82, NAVY, line=None, radius=0.1)
    shape_text(s.shapes[-1],
               [P([R("AGENTRA TECH", WHITE, True, 15, SEMI)], align=PP_ALIGN.CENTER, space_after=1),
                P([R("4 kişilik takım · Kuruluş 2026", C("AEC2E6"), False, 10.5, BODY)],
                  align=PP_ALIGN.CENTER, space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
    # bağlantı: tepe -> yatay bara -> 4 kutu
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
    bus_y = 3.18
    box_y = 3.62
    # dikey (tepe -> bara)
    lineseg(s, top_cx - 0.01, 2.54, 0.02, bus_y - 2.54)
    # yatay bara
    lineseg(s, min(centers) - 0.01, bus_y, (max(centers) - min(centers)) + 0.02, 0.02)
    # 4 dikey (bara -> kutu)
    for cx in centers:
        lineseg(s, cx - 0.01, bus_y, 0.02, box_y - bus_y)
    # kişi kutuları
    bh = 2.15
    for (ini, nm, fn, col, cap), x in zip(people, xs):
        rrect(s, x, box_y, bw, bh, WHITE, line=LINE, line_w=1.25, radius=0.07)
        rect(s, x, box_y, bw, 0.08, col)
        oval(s, x + bw / 2 - 0.34, box_y + 0.2, 0.68, 0.68, col)
        shape_text(s.shapes[-1], [P([R(ini, WHITE, True, 22, SEMI)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 0.1, box_y + 1.0, bw - 0.2, 0.4,
                [P([R(nm, INK, True, 12, SEMI)], align=PP_ALIGN.CENTER, line=0.98)])
        paras = [P([R(seg, col, True, 10.3, SEMI)], align=PP_ALIGN.CENTER, space_after=0, line=1.0)
                 for seg in fn.split("\n")]
        textbox(s, x + 0.08, box_y + 1.44, bw - 0.16, 0.65, paras)
        if cap:
            pill(s, x + bw / 2 - 0.62, box_y - 0.16, 1.24, 0.32, "★ TAKIM KAPTANI", RED, size=8.5)
    # alt not
    rrect(s, 0.62, 6.06, 12.09, 0.74, SOFT, line=LINE, line_w=1.0, radius=0.08)
    textbox(s, 0.95, 6.19, 11.5, 0.5,
            [P([R("Kaptan Şeyma Nur Çebi ekibi koordine eder; kararlar ortak GitHub deposu üzerinden "
                  "şeffaf ve izlenebilir yürür. Her uzmanlık alanı bir sorumluya bağlıdır.",
                  INK, False, 11, BODY)], line=1.05)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 05 — Takım Üyeleri
# ----------------------------------------------------------------------------
def slayt_uyeler(prs, n):
    s = new_slide(prs)
    header(s, "Ekip Üyeleri", "Takım Üyeleri ve Sorumlulukları")
    members = [
        ("Şeyma Nur Çebi", "TAKIM KAPTANI · YAZILIM", SEYMA,
         "Görev 1 içerik analizi: sınıflandırma, bilgi çıkarımı, mevzuat RAG; değerlendirme ve uçtan uca entegrasyon.", True),
        ("Muhammed Sina Gün", "YAZILIM", SINA,
         "Mimari ve orkestrasyon; model-agnostik LLM katmanı; Görev 2 taslak üretimi (OCR ve özet dâhil).", False),
        ("Emine Elik", "VERİ · TEST · DOKÜMAN", EMINE,
         "Veri seti ve etiketleme; test kapsamı; dokümantasyon; sunum ve demo; şartname uyum takibi.", False),
        ("Zeynep Akel", "YAZILIM", ZEYNEP,
         "Görev 1 eksik bilgi tespiti; Görev 2 yönlendirme ve kullanıcı etkileşimi; triyaj, KVKK; web arayüzü.", False),
    ]
    pos = [(0.62, 1.72), (6.72, 1.72), (0.62, 3.94), (6.72, 3.94)]
    cw, ch = 6.0, 2.06
    for (name, role, col, desc, cap), (x, y) in zip(members, pos):
        rrect(s, x, y, cw, ch, WHITE, line=LINE, line_w=1.25, radius=0.07)
        rect(s, x, y, 0.11, ch, col)
        oval(s, x + 0.28, y + 0.28, 0.72, 0.72, col)
        shape_text(s.shapes[-1], [P([R(name[0], WHITE, True, 24, SEMI)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 1.18, y + 0.24, cw - 1.4, 0.4, [P([R(name, INK, True, 15.5, SEMI)])])
        pill(s, x + 1.18, y + 0.66, min(cw - 1.4, 0.5 + len(role) * 0.082), 0.3, role, col, size=9)
        textbox(s, x + 0.3, y + 1.14, cw - 0.55, 0.85,
                [P([R(desc, C("34405A"), False, 10.8, BODY)], line=1.05)])
        if cap:
            pill(s, x + cw - 1.15, y + 0.2, 0.95, 0.3, "★ KAPTAN", RED, size=8.5)
    textbox(s, 0.62, 6.18, 12.1, 0.6,
            [P([R("Her üye için okul/bölüm bilgisi: ", MUTED, False, 10.5, BODY),
                R("[Bölüm / Üniversite — doldurulacak]", RED, False, 10.5, BODY),
                R("      Danışman: ", MUTED, False, 10.5, BODY),
                R("[Ad Soyad — Unvan/Kurum · varsa]", RED, False, 10.5, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 06 — Görev Dağılımı (m.6.4)
# ----------------------------------------------------------------------------
def slayt_gorev_dagilimi(prs, n):
    s = new_slide(prs)
    header(s, "Görev Dağılımı", "Görev Dağılımımız · Şartname m.6.4")
    person_col = {"Şeyma Nur": SEYMA, "Sina": SINA, "Zeynep": ZEYNEP, "Emine": EMINE}

    def panel(x, w, title, acc, rows):
        rrect(s, x, 1.68, w, 4.02, WHITE, line=LINE, line_w=1.25, radius=0.05)
        rrect(s, x, 1.68, w, 0.5, acc, line=None, radius=0.05)
        rect(s, x, 2.02, w, 0.16, acc)
        textbox(s, x, 1.72, w, 0.44, [P([R(title, WHITE, True, 12.5, SEMI)],
                align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
        ry = 2.32
        for j, (cap, who) in enumerate(rows):
            if j % 2 == 1:
                rect(s, x + 0.12, ry, w - 0.24, 0.5, SOFT)
            textbox(s, x + 0.28, ry + 0.12, w - 2.0, 0.32, [P([R(cap, INK, False, 11.5, BODY)])])
            pw = 0.4 + len(who) * 0.095
            pill(s, x + w - pw - 0.28, ry + 0.1, pw, 0.32, who, person_col[who], size=9.5)
            ry += 0.545

    panel(0.62, 6.0, "GÖREV 1 — Sınıflandırma & İçerik Analizi", BLUE, [
        ("OCR / metin okuma", "Sina"),
        ("Tür belirleme (sınıflandırma)", "Şeyma Nur"),
        ("Bilgi çıkarımı", "Şeyma Nur"),
        ("Eksik bilgi tespiti", "Zeynep"),
        ("Mevzuat önerisi (BM25 RAG)", "Şeyma Nur"),
        ("Özet oluşturma", "Sina"),
    ])
    panel(6.72, 6.0, "GÖREV 2 — Taslaklama & Yönlendirme", ORANGE, [
        ("Resmî yazı taslağı", "Sina"),
        ("Format öz-denetimi (üslup)", "Sina"),
        ("Birim yönlendirme", "Zeynep"),
        ("Kullanıcı bilgilendirme", "Zeynep"),
        ("Eksik bilgi talebi", "Zeynep"),
        ("Altyapı: veri · test · doküman", "Emine"),
    ])
    textbox(s, 0.62, 5.86, 6.0, 0.4,
            [P([R("Her yetenek bir sorumluya ve gerçek bir kod modülüne bağlıdır.",
                 MUTED, False, 10.5, BODY)])])
    lx = 7.15
    textbox(s, 6.72, 5.85, 0.5, 0.3, [P([R("Ekip:", MUTED, True, 10, SEMI)])])
    for name, col in person_col.items():
        w = 0.35 + len(name) * 0.093
        pill(s, lx, 5.85, w, 0.3, name, col, size=9)
        lx += w + 0.13
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 07 — Nasıl Çalışıyoruz
# ----------------------------------------------------------------------------
def slayt_calisma(prs, n):
    s = new_slide(prs)
    header(s, "Çalışma Biçimimiz", "Nasıl Çalışıyoruz?")
    pipeline_strip(s, 1.95, [
        ("💡 Fikir", C("41506B")), ("⚙️ Geliştirme", SINA), ("🧪 Test & Ölçüm", BLUE),
        ("📊 Dürüst Rapor", TEAL), ("🔁 İyileştirme", ORANGE),
    ], h=0.72)
    textbox(s, 0.62, 2.8, 12.0, 0.35,
            [P([R("Her özellik; fikirden koda, otomatik testlere ve dürüst ölçüme kadar aynı döngüden geçer.",
                 MUTED, False, 11, BODY)], align=PP_ALIGN.CENTER)])
    cards = [
        ("🔓", "Açık ve İzlenebilir", ["Ortak GitHub deposu (Apache 2.0)",
         "Her karar kayıt altında", "Tüm dokümantasyon Türkçe"], GREEN),
        ("🔄", "Sürekli Entegrasyon", ["En az haftalık commit",
         "500+ otomatik test sürekli yeşil", "Her katkı gözden geçirilir"], BLUE),
        ("🎯", "Dürüst Ölçüm", ["Değerlendirme aracıyla düzenli ölçüm",
         "Tutulmuş (held-out) setler", "Sonuçlar olduğu gibi raporlanır"], RED),
    ]
    x = 0.62; cw = 3.93
    for (ic, tt, bl, ac) in cards:
        card(s, x, 3.4, cw, 3.1, ic, tt, bl, ac)
        x += cw + 0.14
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 08 — Projemiz (kısa tanıtım)
# ----------------------------------------------------------------------------
def slayt_proje(prs, n):
    s = new_slide(prs)
    header(s, "Kısa Proje Tanıtımı", "Ne Geliştiriyoruz?")
    rrect(s, 0.62, 1.72, 12.09, 1.05, SOFT, line=LINE, line_w=1.0, radius=0.06)
    rect(s, 0.62, 1.72, 0.09, 1.05, RED)
    textbox(s, 0.95, 1.86, 11.5, 0.85,
            [P([R("Kamu kurumlarına gelen evrağı ", INK, False, 14, BODY),
                R("okuyan · anlayan · eksiğini bulan · mevzuat öneren · resmî yazı taslaklayan · doğru birime yönlendiren",
                  INK, True, 14, SEMI),
                R(" çok ajanlı bir yapay zekâ sistemi.", INK, False, 14, BODY)], line=1.12),
             P([R("11 uzman ajan + orkestratör · framework bağımsız saf Python · çevrimdışı-öncelikli (offline-first)",
                 MUTED, False, 11.5, BODY)], space_before=3)])
    pipeline_strip(s, 3.05, [
        ("📥 Girdi", C("41506B")), ("🧠 Orkestratör", PURPLE), ("📋 Görev 1", BLUE),
        ("✍️ Görev 2", ORANGE), ("📤 12+ Çıktı", GREEN),
    ], h=0.7)
    # iki görev kartı
    card(s, 0.62, 4.05, 5.95, 2.15, "📋", "Görev 1 — Sınıflandırma & İçerik Analizi",
         ["Metin/PDF/görüntü okuma (OCR) + tür belirleme",
          "Bilgi çıkarımı · eksik bilgi tespiti",
          "İlgili mevzuat önerisi · kısa özet"], BLUE)
    card(s, 6.76, 4.05, 5.95, 2.15, "✍️", "Görev 2 — Taslaklama & Yönlendirme",
         ["Resmî yazı taslağı (Yönetmelik uyumlu)",
          "Gerekçeli birim yönlendirme",
          "Kullanıcı bilgilendirme · eksik bilgi talebi"], ORANGE)
    textbox(s, 0.62, 6.34, 12.1, 0.4,
            [P([R("Ayrıntılı teknik mimari, kod ve canlı demo final aşamasında sunulacaktır.",
                 MUTED, False, 10.5, BODY)], align=PP_ALIGN.CENTER)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 09 — Çalışan Sistem (kanıt)
# ----------------------------------------------------------------------------
def slayt_kanit(prs, n):
    s = new_slide(prs)
    header(s, "Kanıtımız", "Bugüne Kadar Ne Ürettik?")
    tiles = [
        ("Çalışan", "sistem", "CLI + web arayüzü + demo · uçtan uca", GREEN),
        ("500", "+", "Test — sürekli entegrasyonda yeşil", BLUE),
        ("116", "", "Etiketli sentetik kurgu evrak", ORANGE),
        ("0", "", "KVKK sızıntısı (bağımsız denetim)", RED),
    ]
    x = 0.62; tw = 2.97
    for (big, unit, label, acc) in tiles:
        kpi_tile(s, x, 1.78, tw, 1.55, big, unit, label, acc)
        x += tw + 0.12
    # ölçüm kartları
    def olcum(x, w, title, acc, rows):
        rrect(s, x, 3.62, w, 2.05, WHITE, line=LINE, line_w=1.25, radius=0.06)
        rect(s, x, 3.62, w, 0.09, acc)
        textbox(s, x + 0.24, 3.78, w - 0.4, 0.4, [P([R(title, INK, True, 12.5, SEMI)])])
        paras = [P([R(lbl + "  ", INK, False, 11, BODY), R(val, acc, True, 11, SEMI)],
                   space_after=4) for (lbl, val) in rows]
        textbox(s, x + 0.24, 4.24, w - 0.44, 1.4, paras)

    olcum(0.62, 5.95, "Geliştirme seti · 52 evrak", BLUE, [
        ("Sınıflandırma doğruluğu", "1,00"), ("Birim yönlendirme", "0,96"),
        ("Eksik-bilgi tespiti (F1)", "1,00"), ("Mevzuat isabet@3", "0,96"),
    ])
    olcum(6.77, 5.95, "Adversarial tutulmuş set · 16 evrak (dokunulmamış)", ORANGE, [
        ("Sınıflandırma doğruluğu", "0,94"), ("Birim yönlendirme", "1,00"),
        ("Eksik-bilgi tespiti (F1)", "0,83"), ("Mevzuat isabet@3", "0,94"),
    ])
    textbox(s, 0.62, 5.82, 12.1, 0.4,
            [P([R("Kaynak: ", MUTED, True, 10, SEMI),
                R("data/processed/eval_report*.json", INK, False, 10, MONO),
                R("  ·  tamamen çevrimdışı mod  ·  sonuçlar olduğu gibi raporlanır  ·  Apache 2.0 açık kaynak",
                  MUTED, False, 10, BODY)])])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 10 — Motivasyon
# ----------------------------------------------------------------------------
def slayt_motivasyon(prs, n):
    s = new_slide(prs)
    header(s, "Neden Buradayız?", "Katılım Motivasyonumuz")
    items = [
        ("⏱️", "Ölçülebilir verimlilik", "İlk inceleme, taslak ve yönlendirme adımlarında personel zamanı kazanımı.", BLUE),
        ("🔒", "Veri egemenliği & KVKK", "Kişisel veriyi 3. taraf API'ye sızdırmadan, tamamen yerel çalışan yerli çözüm.", RED),
        ("🌍", "Açık kaynak katkısı", "Türkçe dil teknolojileri ekosistemine (TAKP) Apache 2.0 lisanslı katkı.", GREEN),
        ("🧭", "Sorumlu otomasyon", "Emin olmadığı kararda durup insana devreden, gerekçeli ve denetlenebilir tasarım.", PURPLE),
        ("🎓", "Takımın ilgisi", "Türkçe NLP ve kamu süreçlerine dair merak ve ortak çalışma isteği.", ORANGE),
    ]
    pos = [(0.62, 1.78), (4.66, 1.78), (8.7, 1.78), (0.62, 4.0), (4.66, 4.0)]
    cw, ch = 3.9, 2.02
    for (ic, tt, bd, ac), (x, y) in zip(items, pos):
        rrect(s, x, y, cw, ch, WHITE, line=LINE, line_w=1.25, radius=0.08)
        oval(s, x + 0.26, y + 0.26, 0.66, 0.66, C("EEF3FB"))
        shape_text(s.shapes[-1], [P([R(ic, INK, False, 20, BODY)], align=PP_ALIGN.CENTER,
                   space_after=0)], anchor=MSO_ANCHOR.MIDDLE)
        rect(s, x + 0.26, y + ch - 0.34, 0.66, 0.06, ac)
        textbox(s, x + 1.06, y + 0.34, cw - 1.25, 0.55, [P([R(tt, INK, True, 13, SEMI)], line=1.0)])
        textbox(s, x + 0.28, y + 1.08, cw - 0.5, 0.85, [P([R(bd, C("34405A"), False, 10.6, BODY)], line=1.06)])
    rrect(s, 8.7, 4.0, 3.9, 2.02, NAVY, line=None, radius=0.08)
    textbox(s, 8.98, 4.22, 3.4, 1.7,
            [P([R("Kamuya uygun yapay zekâ", GOLD, True, 14, SEMI)], space_after=4),
             P([R("“Her şeyi otomatikleştiren” değil; ", C("D8E2F3"), False, 11.5, BODY),
                R("doğru yerde insana devreden", WHITE, True, 11.5, SEMI),
                R(" bir sistem güven verir.", C("D8E2F3"), False, 11.5, BODY)], line=1.1)])
    footer(s, n)
    return s


# ----------------------------------------------------------------------------
# 11 — Kapanış
# ----------------------------------------------------------------------------
def slayt_kapanis(prs, n):
    s = new_slide(prs, dark=True)
    rect(s, 0, 0, 0.16, H_IN, RED)
    textbox(s, 0.9, 1.15, 11.0, 0.4, [P([R("TEŞEKKÜRLER", RED, True, 15, SEMI)])])
    textbox(s, 0.88, 1.55, 11.2, 1.0, [P([R("AGENTRA TECH", WHITE, True, 42, SEMI)])])
    textbox(s, 0.9, 2.55, 11.4, 0.5,
            [P([R("Organizasyon yapısı, ekip ve görev dağılımıyla; kamuya uygun bir yapay zekâ takımı.",
                 C("D8E2F3"), False, 14, BODY)])])
    members = [("Şeyma Nur Çebi", "Kaptan", SEYMA), ("Muhammed Sina Gün", "", SINA),
               ("Emine Elik", "", EMINE), ("Zeynep Akel", "", ZEYNEP)]
    x = 0.9
    for (nm, rl, col) in members:
        w = 0.5 + len(nm) * 0.11 + (len(rl) * 0.09 if rl else 0)
        rrect(s, x, 3.35, w, 0.55, NAVY2, line=None, radius=0.3)
        oval(s, x + 0.16, 3.5, 0.25, 0.25, col)
        runs = [R(nm, WHITE, True, 11.5, SEMI)]
        if rl:
            runs.append(R("  · " + rl, C("9FB4D8"), False, 10, BODY))
        textbox(s, x + 0.5, 3.46, w - 0.5, 0.35, [P(runs)])
        x += w + 0.2
    rrect(s, 0.9, 4.35, 7.7, 0.7, NAVY2, line=None, radius=0.1)
    textbox(s, 1.15, 4.5, 7.3, 0.4,
            [P([R("Depo:  ", C("9FB4D8"), True, 12, SEMI),
                R("github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan", WHITE, False, 12, MONO)])])
    rrect(s, 0.9, 5.2, 7.7, 0.7, NAVY2, line=None, radius=0.1)
    textbox(s, 1.15, 5.35, 7.3, 0.4,
            [P([R("İletişim:  ", C("9FB4D8"), True, 12, SEMI),
                R("[takım e-postası — doldurulacak]", C("F3B7C0"), False, 12, BODY)])])
    textbox(s, 0.9, 6.35, 11.4, 0.6,
            [P([R("Kamuya uygun, dürüst, açık kaynak ve ", C("C7D5EC"), False, 13.5, BODY),
                R("bugün çalışan", WHITE, True, 13.5, SEMI),
                R(" bir sistem geliştiren bir takımız.", C("C7D5EC"), False, 13.5, BODY)])])
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
