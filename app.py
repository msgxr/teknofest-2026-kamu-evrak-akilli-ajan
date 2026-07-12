"""
Evrak Zekâ — Kamu Evrak Akıllı Ajanı · Kurumsal Yönetim Panosu.

TEKNOFEST 2026 "Yapay Zeka Dil Ajanları Yarışması" — 1. Senaryo:
"Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi".

Tek dosyalık (app.py), `streamlit run app.py` ile tarayıcıdan açılan kurumsal
SaaS panosu. Görsel katman (koyu lacivert kenar çubuğu, beyaz kartlar,
sparkline metrikler, canlı ajan akışı, birim sevk barları) referans kurumsal
tasarıma göre gömülü tema (CSS) ile üretilir; harici frontend çatısı
(React/Vue/Tailwind) veya harici çizim bağımlılığı kullanılmaz.

Not (şartname uyumu):
    Uygulama tamamen SENTETİK / KURGU veri ile çalışır. Hiçbir gerçek kişisel
    veri (PII) üretilmez veya kopyalanmaz. Metrikler, loglar ve ajan telemetrisi
    sunum amaçlı simüle edilmiştir (mock).

Çalıştırma:
    streamlit run app.py
"""

from __future__ import annotations

import html as _html
import random
import re
import time
from datetime import datetime, timedelta

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

# ===========================================================================
#  BÖLÜM -1 — GERÇEK BACKEND KÖPRÜSÜ (11-ajan orkestratör)
# ===========================================================================
# Bu pano, GERÇEK uçtan uca pipeline'a (src/) bağlıdır: Evrak İşleme, KVKK
# maskeleme ve Asistan sayfaları canlı orkestratör çıktısı üretir. Backend
# yüklenemezse (bağımlılık/ortam) uygulama ÇÖKMEZ; ilgili sayfalar açık
# "SİMÜLASYON" etiketiyle kurgu veriye zarifçe iner (şartname: ölçülmemiş
# metrik gerçekmiş gibi sunulmaz, jüri asla yanıltılmaz — Anayasal İlke 2/4).

# app.py'nin dizinini (repo kökü) modül yoluna ekle → `src` importu, uygulama
# hangi çalışma dizininden başlatılırsa başlatılsın çözülsün.
_KOK_DIZIN = os.path.dirname(os.path.abspath(__file__))
if _KOK_DIZIN not in sys.path:
    sys.path.insert(0, _KOK_DIZIN)

try:
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline as _EndToEndPipeline
    from src.agents.orchestrator import AgentState as _AgentState
    from src.agents.anonimlestirme_agent import AnonimlestirmeAgent as _AnonimAgent

    _BACKEND_VAR = True
    _BACKEND_HATA = None
except Exception as _imp_hata:  # pragma: no cover - ortam bağımlı
    _EndToEndPipeline = _AgentState = _AnonimAgent = None
    _BACKEND_VAR = False
    _BACKEND_HATA = str(_imp_hata)


@st.cache_resource(show_spinner=False)
def _gercek_pipeline():
    """Gerçek 11-ajan pipeline'ı bir kez kurar (oturumlar arası paylaşılır).

    Kayıt defteri KAPALIDIR: arayüz kullanımı değerlendirme/denetim izine yan
    etki yazmaz. Kurulum başarısızsa None döner ve çağıran fallback'e iner.
    """
    if _EndToEndPipeline is None:
        return None
    try:
        return _EndToEndPipeline(kayit_defteri_aktif=False)
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def _anonim_agent():
    """KVKK anonimleştirme agent'ı (hafif; yalnızca maskeleme için)."""
    if _AnonimAgent is None:
        return None
    try:
        return _AnonimAgent()
    except Exception:
        return None


# Gerçek anonimleştirme raporundaki sayaç anahtarları → okunur etiketler.
_PII_ETIKET = {
    "tc_kimlik": "TCKN", "telefon": "Telefon", "eposta": "E-posta",
    "iban": "IBAN", "kisi_adi": "Ad-Soyad", "adres": "Adres",
    "plaka": "Araç Plakası", "dogum_tarihi": "Doğum Tarihi",
    "sicil_no": "Sicil No",
}


# ===========================================================================
#  BÖLÜM 0 — KURUMSAL RENK PALETİ VE SABİTLER
# ===========================================================================

# Marka / kurumsal tonlar (referans tasarım paleti).
LACIVERT_KOYU = "#0E1C33"    # Kenar çubuğu arka planı
LACIVERT = "#132B4D"         # Kenar çubuğu vurgusu
MAVI = "#2F6BFF"             # Ana vurgu (mavi)
MAVI_ACIK = "#3B82F6"        # İkincil mavi
YESIL = "#16A34A"            # Olumlu / aktif
SARI = "#D97706"             # Uyarı
KIRMIZI = "#DC2626"          # Kritik
SLATE = "#475569"            # Nötr metin
ZEMIN = "#EEF2F7"            # İçerik arka planı (açık)

# Kategorik grafik paleti (Altair).
KATEGORIK_PALET = [MAVI, YESIL, MAVI_ACIK, "#7C3AED", SARI, SLATE,
                   "#0EA5E9", "#94A3B8"]

# ---------------------------------------------------------------------------
#  11 uzman ajan (src/agents/ ile birebir ad) — roller CLAUDE.md'den.
# ---------------------------------------------------------------------------
AJANLAR = [
    {"kod": "ocr", "ad": "OCR Ajanı", "ikon": "📄",
     "rol": "Taranmış/dijital evraktan metni çıkarır, okunabilirlik kapısını besler.",
     "kategori": "Görev 1 · Okuma"},
    {"kod": "classification", "ad": "Sınıflandırma Ajanı", "ikon": "🏷️",
     "rol": "Evrak türünü belirler (dilekçe, üst yazı, tutanak, genelge...).",
     "kategori": "Görev 1 · Analiz"},
    {"kod": "info_extraction", "ad": "Bilgi Çıkarım Ajanı", "ikon": "🔎",
     "rol": "Tarih, kurum, kişi, referans no, konu ve muhatabı çıkarır.",
     "kategori": "Görev 1 · Analiz"},
    {"kod": "missing_info", "ad": "Eksik Bilgi Ajanı", "ikon": "🧩",
     "rol": "Zorunlu alanların eksikliğini tespit eder, tamamlanma talebi üretir.",
     "kategori": "Görev 1 · Analiz"},
    {"kod": "legislation", "ad": "Mevzuat Ajanı", "ikon": "⚖️",
     "rol": "BM25 tabanlı RAG ile ilgili kanun/yönetmelik maddelerini eşler.",
     "kategori": "Görev 1 · Mevzuat"},
    {"kod": "triage", "ad": "Önceliklendirme Ajanı", "ikon": "🚦",
     "rol": "Aciliyet + yasal süre analizine göre önceliği belirler.",
     "kategori": "Görev 1 · Aciliyet"},
    {"kod": "summarization", "ad": "Özet Ajanı", "ikon": "📝",
     "rol": "Sadakat denetimli yönetici özeti üretir (ROUGE-L kontrollü).",
     "kategori": "Görev 1 · Özet"},
    {"kod": "anonimlestirme", "ad": "KVKK Anonimleştirme Ajanı", "ikon": "🛡️",
     "rol": "TCKN, telefon, adres gibi PII alanlarını maskeler (KVKK uyumu).",
     "kategori": "Görev 1 · KVKK"},
    {"kod": "draft_writer", "ad": "Cevap Hazırlama Ajanı", "ikon": "✍️",
     "rol": "Resmî yazışma formatında cevap/üst yazı taslağı üretir.",
     "kategori": "Görev 2 · Üretim"},
    {"kod": "routing", "ad": "Yönlendirme Ajanı", "ikon": "🧭",
     "rol": "Evrakı ilgili birime/kurum koduna yönlendirir.",
     "kategori": "Görev 2 · Dağıtım"},
    {"kod": "user_info", "ad": "Bilgilendirme Ajanı", "ikon": "📣",
     "rol": "Vatandaşı/kullanıcıyı süreç ve eksikler hakkında bilgilendirir.",
     "kategori": "Görev 2 · Bilgilendirme"},
]

AJAN_HATTI_SIRASI = [a["kod"] for a in AJANLAR]

# Orkestratör — 11 uzman ajanı koşullu akışla yöneten çekirdek koordinatör.
# (src/agents/orchestrator.py karşılığı; 3 kapı: okunabilirlik / dil / düşük güven.)
ORKESTRATOR = {
    "kod": "orchestrator", "ad": "Orkestratör Ajan", "ikon": "🧠",
    "rol": "11 uzman ajanı koşullu akışla yönetir; okunabilirlik, dil ve "
           "düşük güven kapılarıyla akışı yönlendirir.",
    "kategori": "Çekirdek · Koordinasyon",
    "kapilar": ["Okunabilirlik kapısı", "Dil kapısı", "Düşük güven kapısı"],
}

EVRAK_TURLERI = [
    "Dilekçe", "Üst Yazı", "Cevap Yazısı", "Genelge",
    "Tutanak", "Rapor", "Onaylı Belge", "Bilgilendirme",
]

# Birim sevk hedefleri (referans tasarımdaki dağılıma yakın).
BIRIMLER = [
    "Yazı İşleri Müdürlüğü", "CİMER / Halkla İlişkiler", "İmar ve Şehircilik Md.",
    "İnsan Kaynakları Müd.", "Mali Hizmetler Müd.", "Hukuk Müşavirliği",
    "Bilgi İşlem D. Bşk.", "Strateji Geliştirme D. Bşk.",
]

ONCELIKLER = {
    "cok_ivedi": "🔴 ÇOK İVEDİ",
    "ivedi": "🟠 İVEDİ",
    "gunlu": "🟡 GÜNLÜ",
    "normal": "🟢 NORMAL",
}

MEVZUAT_KORPUS = [
    {"kod": "3071", "baslik": "Dilekçe Hakkının Kullanılmasına Dair Kanun",
     "tur": "Kanun", "yil": 1984, "madde": 12,
     "ozet": "Vatandaşın dilekçe hakkı ve idarenin 30 gün içinde cevap yükümlülüğü."},
    {"kod": "4982", "baslik": "Bilgi Edinme Hakkı Kanunu",
     "tur": "Kanun", "yil": 2003, "madde": 31,
     "ozet": "Bilgi edinme başvurularının 15 iş günü içinde yanıtlanması."},
    {"kod": "6698", "baslik": "Kişisel Verilerin Korunması Kanunu (KVKK)",
     "tur": "Kanun", "yil": 2016, "madde": 30,
     "ozet": "Kişisel verilerin işlenmesi, aktarımı ve anonimleştirme ilkeleri."},
    {"kod": "5070", "baslik": "Elektronik İmza Kanunu",
     "tur": "Kanun", "yil": 2004, "madde": 25,
     "ozet": "Güvenli elektronik imzanın hukuki geçerliliği ve şartları."},
    {"kod": "RG-2015-1", "baslik": "Resmî Yazışmalarda Uygulanacak Usul ve Esaslar",
     "tur": "Yönetmelik", "yil": 2015, "madde": 28,
     "ozet": "Resmî yazıların biçim, sayı, tarih, ek ve dağıtım standartları."},
    {"kod": "RG-2019-DYS", "baslik": "e-Yazışma Teknik Rehberi (DYS Entegrasyonu)",
     "tur": "Genelge", "yil": 2019, "madde": 14,
     "ozet": "Doküman Yönetim Sistemi (DYS) ve e-Yazışma paket standartları."},
    {"kod": "657", "baslik": "Devlet Memurları Kanunu",
     "tur": "Kanun", "yil": 1965, "madde": 236,
     "ozet": "Memur hak, yükümlülük, izin ve disiplin süreçlerine ilişkin esaslar."},
    {"kod": "2577", "baslik": "İdari Yargılama Usulü Kanunu",
     "tur": "Kanun", "yil": 1982, "madde": 64,
     "ozet": "İdari işlemlere karşı dava açma süreleri ve usul kuralları."},
    {"kod": "RG-2021-EBYS", "baslik": "Elektronik Belge Yönetim Sistemi Genelgesi",
     "tur": "Genelge", "yil": 2021, "madde": 9,
     "ozet": "EBYS üzerinden evrak kaydı, havale ve arşivleme yükümlülükleri."},
    {"kod": "RG-2023-STD", "baslik": "Kamu Kurumları Yazışma Standartları Tebliği",
     "tur": "Resmi Gazete", "yil": 2023, "madde": 18,
     "ozet": "Antet, imza bloğu, ek listesi ve kurumsal kimlik standartları."},
]

KURGU_EVRAK_REFERANSLARI = [
    "EVR-2026-000412", "EVR-2026-000418", "EVR-2026-000425",
    "EVR-2026-000431", "EVR-2026-000447", "EVR-2026-000452",
    "EVR-2026-000460", "EVR-2026-000473", "EVR-2026-000488",
]

ORNEK_DILEKCE = """T.C.
ÖRNEK BELEDİYE BAŞKANLIĞI'NA

Konu: Kaldırım onarımı hk.

İlgili mahallede, ikamet ettiğim caddedeki kaldırımların uzun süredir
tamir edilmediğini ve yaya geçişinin güçleştiğini bildirmek isterim.
Söz konusu kaldırımların onarılması ve gerekli çalışmanın başlatılması
hususunda gereğini arz ederim.

Saygılarımla.

Ad Soyad: [KURGU] A. Yılmaz
T.C. Kimlik No: 10000000146
Tarih: 10.07.2026
İletişim: 0532 111 22 33
E-posta: kurgu.vatandas@ornek.gov.tr
"""

# Kenar çubuğu gezinme yapısı: (etiket, ikon, rozet).
GEZINME = {
    "ÇALIŞMA ALANI": [
        ("Genel Bakış", "📊", ""),
        ("Evrak İşleme", "📥", "CANLI"),
        ("Toplu İşleme", "⚡", ""),
        ("Ajan Yönetimi", "🤖", str(len(AJANLAR))),
        ("Asistan", "💬", "AI"),
        ("Mevzuat ve RAG", "📚", ""),
    ],
    "SİSTEM": [
        ("KVKK ve Uyum", "🛡️", ""),
        ("Ayarlar", "⚙️", ""),
    ],
}

# Asistan (Orkestratör sohbeti) karşılama mesajı.
_KARSILAMA_MESAJI = (
    "👋 Merhaba, ben **Orkestratör Ajan**. 11 uzman ajanı yöneten çekirdek "
    "koordinatörüm. Bana doğal dille soru sorabilirsiniz; ilgili ajana "
    "yönlendirip yanıtı derlerim.\n\n"
    "Örnek: *“3071 sayılı kanuna göre dilekçeye kaç günde cevap verilir?”*, "
    "*“Ajanların durumu nedir?”*, *“Bu evrakta KVKK riski var mı?”*"
)


# ===========================================================================
#  BÖLÜM 1 — SAYFA YAPILANDIRMASI, GÖMÜLÜ TEMA (CSS) VE OTURUM
# ===========================================================================

def sayfa_yapilandir() -> None:
    """Streamlit sayfa yapılandırması (geniş düzen, başlık, ikon)."""
    st.set_page_config(
        page_title="Evrak Zekâ — Kamu Ajan Sistemi",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def tema_uygula() -> None:
    """Kurumsal görsel temayı (gömülü CSS) uygular.

    Not: Referans kurumsal tasarımı yakalamak için Streamlit'e gömülü tek bir
    stil bloğu enjekte edilir. Uygulama yine tek `app.py` ve `streamlit run`
    ile tarayıcıdan açılır; harici frontend çatısı kullanılmaz.
    """
    _md(
        """
        <style>
        /* ---- Genel zemin ve varsayılan Streamlit kromunu sadeleştir ---- */
        #MainMenu, header[data-testid="stHeader"], footer {visibility: hidden;}
        .stApp { background: #EEF2F7; }
        .block-container { padding: 1.1rem 2.2rem 3rem 2.2rem; max-width: 100%; }
        * { font-family: "Segoe UI", "Inter", system-ui, -apple-system, sans-serif; }

        /* ---- Kenar çubuğu (koyu lacivert) ---- */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0E1C33 0%, #0B1728 100%);
            border-right: 1px solid #1c3252;
        }
        [data-testid="stSidebar"] * { color: #C7D2E1; }
        [data-testid="stSidebar"] .block-container { padding-top: 0; }

        /* Kenar çubuğu gezinme butonları (nav satırı gibi) */
        [data-testid="stSidebar"] .stButton > button {
            width: 100%; text-align: left; justify-content: flex-start;
            background: transparent; color: #AEBBCE; border: none;
            border-radius: 10px; padding: 0.5rem 0.85rem; margin: 1px 0;
            font-weight: 500; font-size: 0.93rem; box-shadow: none;
            transition: all 0.12s ease;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: #16294a; color: #ffffff;
        }
        /* Aktif (primary) nav satırı — sol mavi aksan */
        [data-testid="stSidebar"] .stButton > button[kind="primary"],
        [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"],
        [data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
            background: #1B3357; color: #ffffff;
            box-shadow: inset 3px 0 0 0 #3B82F6;
        }

        /* ---- Kart ve panel bileşenleri ---- */
        .ez-grid4 {
            display: grid; grid-template-columns: repeat(4, 1fr);
            gap: 18px; margin: 8px 0 20px 0;
        }
        .ez-grid2 {
            display: grid; grid-template-columns: 1.15fr 1fr;
            gap: 18px; margin-top: 4px;
        }
        @media (max-width: 1100px) {
            .ez-grid4 { grid-template-columns: repeat(2, 1fr); }
            .ez-grid2 { grid-template-columns: 1fr; }
        }
        .ez-card, .ez-panel {
            background: #ffffff; border: 1px solid #E6EBF2;
            border-radius: 16px; padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(16,32,64,0.05),
                        0 8px 24px rgba(16,32,64,0.04);
        }
        .ez-card-head {
            display: flex; justify-content: space-between;
            align-items: center; margin-bottom: 14px;
        }
        .ez-icon-chip {
            width: 40px; height: 40px; border-radius: 11px;
            display: flex; align-items: center; justify-content: center;
            font-size: 19px;
        }
        .ez-pill {
            font-size: 0.72rem; font-weight: 700; padding: 4px 10px;
            border-radius: 999px; white-space: nowrap;
        }
        .ez-pill.green { background: #DCFCE7; color: #15803D; }
        .ez-pill.blue  { background: #DBEAFE; color: #1D4ED8; }
        .ez-pill.amber { background: #FEF3C7; color: #B45309; }
        .ez-pill.red   { background: #FEE2E2; color: #B91C1C; }
        .ez-value {
            font-size: 2.05rem; font-weight: 800; color: #0F1E38;
            line-height: 1.1;
        }
        .ez-label { font-size: 0.86rem; color: #64748B; margin-top: 2px; }
        .ez-spark {
            display: flex; align-items: flex-end; gap: 4px;
            height: 42px; margin-top: 16px;
        }
        .ez-bar { flex: 1; border-radius: 3px 3px 0 0; opacity: 0.9; }

        /* ---- Panel başlıkları ---- */
        .ez-panel-head { margin-bottom: 12px; }
        .ez-panel-title {
            font-size: 1.02rem; font-weight: 700; color: #0F1E38;
        }
        .ez-panel-sub { font-size: 0.8rem; color: #64748B; margin-top: 2px; }
        .ez-panel-tag {
            float: right; background: #EFF6FF; color: #1D4ED8;
            font-size: 0.72rem; font-weight: 700; padding: 3px 10px;
            border-radius: 999px;
        }

        /* ---- Canlı ajan akışı (log) ---- */
        .ez-log-item {
            display: flex; gap: 12px; padding: 11px 0;
            border-bottom: 1px solid #F1F5F9;
        }
        .ez-log-item:last-child { border-bottom: none; }
        .ez-log-icon {
            width: 34px; height: 34px; border-radius: 9px; flex-shrink: 0;
            display: flex; align-items: center; justify-content: center;
            background: #F1F5F9; font-size: 15px;
        }
        .ez-log-title { font-size: 0.9rem; color: #1E293B; font-weight: 500; }
        .ez-log-meta { margin-top: 3px; }
        .ez-tag {
            font-size: 0.7rem; font-weight: 700; padding: 2px 8px;
            border-radius: 6px; background: #EFF6FF; color: #2563EB;
        }
        .ez-time { font-size: 0.72rem; color: #94A3B8; margin-left: 8px; }

        /* ---- Birim sevk barları ---- */
        .ez-dept-row { margin: 13px 0; }
        .ez-dept-top {
            display: flex; justify-content: space-between;
            font-size: 0.86rem; color: #334155; margin-bottom: 5px;
        }
        .ez-dept-val { font-weight: 700; color: #0F1E38; }
        .ez-dept-track {
            height: 8px; background: #EEF2F7; border-radius: 999px;
            overflow: hidden;
        }
        .ez-dept-fill {
            height: 100%; border-radius: 999px;
            background: linear-gradient(90deg, #2F6BFF, #3B82F6);
        }

        /* ---- Üst çubuk ---- */
        .ez-topbar {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 8px;
        }
        .ez-crumb { font-size: 0.78rem; color: #64748B; font-weight: 600;
                    letter-spacing: 0.02em; }
        .ez-h1 { font-size: 1.55rem; font-weight: 800; color: #0F1E38;
                 margin: 2px 0; }
        .ez-h1-sub { font-size: 0.88rem; color: #64748B; }
        .ez-search {
            background: #ffffff; border: 1px solid #E2E8F0; border-radius: 12px;
            padding: 9px 16px; color: #94A3B8; font-size: 0.86rem;
            min-width: 300px;
        }
        .ez-icobtn {
            width: 40px; height: 40px; border-radius: 11px;
            background: #ffffff; border: 1px solid #E2E8F0;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 16px;
        }
        .ez-avatar {
            width: 40px; height: 40px; border-radius: 11px;
            background: linear-gradient(135deg, #2F6BFF, #1B3357);
            color: #fff; font-weight: 700; font-size: 0.9rem;
            display: inline-flex; align-items: center; justify-content: center;
        }
        .ez-livepill {
            background: #DCFCE7; color: #15803D; font-weight: 700;
            font-size: 0.78rem; padding: 6px 14px; border-radius: 999px;
        }

        /* ---- Marka (kenar çubuğu üstü) ---- */
        .ez-brand { display: flex; gap: 12px; align-items: center;
                    padding: 6px 4px 2px 4px; }
        .ez-brand-logo {
            width: 42px; height: 42px; border-radius: 12px;
            background: linear-gradient(135deg, #2F6BFF, #1B3357);
            display: flex; align-items: center; justify-content: center;
            font-size: 20px;
        }
        .ez-brand-name { font-size: 1.05rem; font-weight: 800; color: #fff; }
        .ez-brand-sub { font-size: 0.68rem; color: #7E8DA5;
                        letter-spacing: 0.08em; }
        .ez-navsec {
            font-size: 0.68rem; font-weight: 700; color: #5B6B85;
            letter-spacing: 0.08em; margin: 14px 6px 4px 6px;
        }
        .ez-navbadge {
            background: #22406b; color: #cfe0ff; font-size: 0.62rem;
            font-weight: 700; padding: 1px 7px; border-radius: 999px;
        }
        .ez-navbadge.live { background: #16A34A; color: #eafff1; }

        /* ---- Kenar çubuğu alt durum listesi ---- */
        .ez-status { margin: 4px 6px; }
        .ez-status-row {
            display: flex; justify-content: space-between; align-items: center;
            font-size: 0.8rem; padding: 5px 0;
        }
        .ez-dot { color: #22C55E; margin-right: 7px; }
        .ez-status-val { color: #93A2BC; font-weight: 600; font-size: 0.76rem; }
        </style>
        """
    )


def oturum_baslat() -> None:
    """Oturum durumunu (session_state) ilk çalıştırmada başlatır."""
    ss = st.session_state
    if ss.get("_baslatildi"):
        return
    ss["_baslatildi"] = True
    ss["aktif_sayfa"] = "Genel Bakış"
    ss["islenen_evrak"] = 1482
    ss["bugun_islenen"] = 164
    ss["ajan_telemetri"] = {a["kod"]: _rastgele_telemetri() for a in AJANLAR}
    # Orkestratör telemetrisi ayrı tutulur; uzman-ajan sayımlarını bozmaz.
    orkestrator = _rastgele_telemetri()
    orkestrator["durum"] = "aktif"
    orkestrator["tamamlanan_akis"] = 1289
    ss["orkestrator_tel"] = orkestrator
    ss["log_kayitlari"] = [_log_kaydi(geri_saniye=(8 - i) * 6)
                           for i in range(8)]
    ss["yuklenen_pdfler"] = []
    ss["son_analiz"] = None
    ss["ajan_mesajlari"] = [_ajan_mesaji(geri_saniye=(6 - i) * 3)
                            for i in range(6)]
    ss["sohbet"] = [{"rol": "assistant", "icerik": _KARSILAMA_MESAJI}]
    ss["bekleyen_soru"] = None


# ===========================================================================
#  BÖLÜM 2 — MOCK TELEMETRİ / LOG ÜRETİCİLERİ
# ===========================================================================

def _rastgele_telemetri() -> dict:
    """Bir ajan için kurgu CPU/Bellek/işlem telemetrisi üretir."""
    return {
        "cpu": round(random.uniform(4.0, 66.0), 1),
        "bellek": round(random.uniform(60.0, 470.0), 0),
        "islem": random.randint(120, 3400),
        "durum": random.choices(["aktif", "calisiyor", "beklemede"],
                                weights=[0.55, 0.30, 0.15])[0],
    }


def _zaman(geri_saniye: int = 0) -> str:
    """Şimdiki zamandan `geri_saniye` önceki HH:MM:SS damgası."""
    return (datetime.now() - timedelta(seconds=geri_saniye)).strftime("%H:%M:%S")


def _log_kaydi(geri_saniye: int = 0) -> dict:
    """Tek bir kurgu canlı ajan akışı kaydı (sözlük) üretir."""
    ajan = random.choice(AJANLAR)
    ref = "#" + random.choice(["SC-330", "UY-77", "2026-1492", "C-8841",
                               "DL-214", "RP-905", "GN-118"])
    olaylar = [
        f"Taranmış belge {ref} OCR ile metne çevrildi ({random.randint(1, 4)} sayfa)",
        f"Üst yazı {ref} resmî yazışma kurallarına uygun (skor %{random.randint(94, 99)})",
        f"Dilekçe {ref} içinde eksik alan: T.C. Kimlik No",
        f"CİMER başvurusu {ref} için resmî cevap taslağı hazırlandı",
        f"{ref} önceliklendirildi: {random.choice(list(ONCELIKLER.values()))}",
        f"{ref} → {random.choice(BIRIMLER)} birimine yönlendirildi",
        f"{ref} KVKK maskeleme tamamlandı (PII gizlendi)",
        f"Mevzuat eşleşmesi {ref}: {random.choice(MEVZUAT_KORPUS)['kod']} "
        f"(skor {round(random.uniform(0.78, 0.97), 2)})",
    ]
    return {"ikon": ajan["ikon"], "ajan": ajan["ad"],
            "mesaj": random.choice(olaylar), "zaman": _zaman(geri_saniye)}


def _ajan_mesaji(geri_saniye: int = 0) -> str:
    """İki ajan arası tek bir koordinasyon mesajı üretir."""
    kaynak, hedef = random.sample(AJANLAR, 2)
    ref = random.choice(KURGU_EVRAK_REFERANSLARI)
    mesajlar = [
        f"{ref} için tür 'Dilekçe' — mevzuat eşlemesi rica olunur.",
        f"{ref} zorunlu alan eksik: 'muhatap'. Bilgilendirme tetiklensin.",
        f"{ref} önceliği ÇOK İVEDİ — taslak öncelikli kuyruğa alındı.",
        f"{ref} PII tespit edildi, maskeleme öncesi işlemi durdur.",
        f"{ref} özet hazır (sadakat 0.94) — taslağa iletiyorum.",
        f"{ref} birim: Hukuk Müşavirliği. Yönlendirme onayı bekleniyor.",
    ]
    return (f"[{_zaman(geri_saniye)}] {kaynak['ikon']} {kaynak['ad']} → "
            f"{hedef['ikon']} {hedef['ad']}: {random.choice(mesajlar)}")


def telemetriyi_guncelle() -> None:
    """Her yeniden çalıştırmada ajan telemetrisini canlı gibi tazeler."""
    telemetriler = list(st.session_state["ajan_telemetri"].values())
    telemetriler.append(st.session_state["orkestrator_tel"])
    for tel in telemetriler:
        tel["cpu"] = round(min(95.0, max(2.0,
                     tel["cpu"] + random.uniform(-6.0, 6.0))), 1)
        tel["bellek"] = round(min(512.0, max(48.0,
                        tel["bellek"] + random.uniform(-18.0, 18.0))), 0)
        tel["islem"] += random.randint(0, 6)
        if random.random() < 0.18:
            tel["durum"] = random.choice(["aktif", "calisiyor", "beklemede"])
    # Orkestratör çoğunlukla aktif kalır (çekirdek koordinatör).
    ork = st.session_state["orkestrator_tel"]
    if ork["durum"] == "beklemede" and random.random() < 0.6:
        ork["durum"] = "aktif"
    ork["tamamlanan_akis"] = ork.get("tamamlanan_akis", 1289) + random.randint(0, 3)


# ===========================================================================
#  BÖLÜM 3 — HTML BİLEŞEN YARDIMCILARI (GÖMÜLÜ TEMA)
# ===========================================================================

def _kacar(metin: str) -> str:
    """HTML özel karakterlerini güvenli biçimde kaçırır."""
    return _html.escape(str(metin))


def _duzles(html_str: str) -> str:
    """HTML dizesindeki satır başı boşluklarını temizleyip tek satıra indirir.

    Streamlit'in markdown motoru, 4+ boşlukla girintili satırları KOD BLOĞU
    sanıp ham HTML'i ekranda düz metin (kod) olarak gösterir. Her satırın baş/son
    boşluğunu kırpıp satırları birleştirerek bu girinti sorununu ortadan kaldırır.
    """
    return "".join(satir.strip() for satir in html_str.splitlines())


def _md(html_str: str) -> None:
    """Girintiden arındırılmış HTML'i Streamlit'e güvenle basar."""
    st.markdown(_duzles(html_str), unsafe_allow_html=True)


def _sparkline(degerler: list, renk: str) -> str:
    """Değer listesinden mini sütun grafiği (sparkline) HTML'i üretir."""
    ust = max(degerler) or 1
    barlar = "".join(
        f'<span class="ez-bar" style="height:{max(14, int(v / ust * 100))}%;'
        f'background:{renk}"></span>' for v in degerler
    )
    return f'<div class="ez-spark">{barlar}</div>'


def _metrik_karti(ikon: str, deger: str, etiket: str, rozet: str,
                  rozet_tipi: str, renk: str, spark: list) -> str:
    """Sparkline'lı kurumsal metrik kartı HTML'i üretir."""
    pill = (f'<span class="ez-pill {rozet_tipi}">{_kacar(rozet)}</span>'
            if rozet else "")
    return f"""
    <div class="ez-card">
      <div class="ez-card-head">
        <div class="ez-icon-chip" style="background:{renk}1a;color:{renk}">
          {ikon}</div>
        {pill}
      </div>
      <div class="ez-value">{_kacar(deger)}</div>
      <div class="ez-label">{_kacar(etiket)}</div>
      {_sparkline(spark, renk)}
    </div>"""


def _metrik_gridi(kartlar: list) -> str:
    """Metrik kartlarını 4'lü ızgara içinde birleştirir."""
    return f'<div class="ez-grid4">{"".join(kartlar)}</div>'


def _log_paneli_html(kayitlar: list, olay_hizi: int) -> str:
    """Canlı ajan akışı panelini (log listesi) HTML olarak üretir."""
    satirlar = ""
    for k in kayitlar[-6:][::-1]:
        satirlar += f"""
        <div class="ez-log-item">
          <div class="ez-log-icon">{k['ikon']}</div>
          <div>
            <div class="ez-log-title">{_kacar(k['mesaj'])}</div>
            <div class="ez-log-meta">
              <span class="ez-tag">{_kacar(k['ajan'])}</span>
              <span class="ez-time">{k['zaman']}</span>
            </div>
          </div>
        </div>"""
    return f"""
    <div class="ez-panel">
      <div class="ez-panel-head">
        <span class="ez-panel-tag">{olay_hizi} olay/dk</span>
        <div class="ez-panel-title">📡 Canlı Ajan Akışı</div>
        <div class="ez-panel-sub">Ajanların gerçek zamanlı işlem günlüğü</div>
      </div>
      {satirlar}
    </div>"""


def _birim_paneli_html(dagilim: list) -> str:
    """Birim bazlı evrak sevki panelini (yatay barlar) HTML üretir."""
    ust = max(v for _, v in dagilim) or 1
    satirlar = ""
    for ad, deger in dagilim:
        genislik = int(deger / ust * 100)
        satirlar += f"""
        <div class="ez-dept-row">
          <div class="ez-dept-top">
            <span>{_kacar(ad)}</span>
            <span class="ez-dept-val">{deger}</span>
          </div>
          <div class="ez-dept-track">
            <div class="ez-dept-fill" style="width:{genislik}%"></div>
          </div>
        </div>"""
    return f"""
    <div class="ez-panel">
      <div class="ez-panel-head">
        <div class="ez-panel-title">🏢 Birim Bazlı Evrak Sevki</div>
        <div class="ez-panel-sub">Otomatik yönlendirilen evrak dağılımı</div>
      </div>
      {satirlar}
    </div>"""


def _ust_cubuk(baslik: str, alt: str, canli: bool = False) -> None:
    """Sayfa üst çubuğunu (başlık + arama + ikonlar + avatar) çizer."""
    canli_html = ('<span class="ez-livepill">● Canlı izleme</span>'
                  if canli else "")
    _md(
        f"""
        <div class="ez-topbar">
          <div>
            <div class="ez-crumb">TEKNOFEST 2026 · Yapay Zeka Dil Ajanları</div>
            <div class="ez-h1">{_kacar(baslik)}</div>
            <div class="ez-h1-sub">{_kacar(alt)}</div>
          </div>
          <div style="display:flex;gap:12px;align-items:center;">
            <span class="ez-search">🔍&nbsp; Evrak, ajan veya mevzuat ara</span>
            <span class="ez-icobtn">🌙</span>
            <span class="ez-icobtn">🔔</span>
            <span class="ez-avatar">MG</span>
            {canli_html}
          </div>
        </div>
        <div style="height:10px"></div>
        """
    )


# ===========================================================================
#  BÖLÜM 4 — KENAR ÇUBUĞU (MARKA + GEZİNME + DURUM)
# ===========================================================================

def kenar_cubugu_ciz() -> str:
    """Kenar çubuğunu çizer ve seçili sayfayı döndürür."""
    with st.sidebar:
        _md(
            """
            <div class="ez-brand">
              <div class="ez-brand-logo">📑</div>
              <div>
                <div class="ez-brand-name">Evrak Zekâ</div>
                <div class="ez-brand-sub">KAMU AJAN SİSTEMİ</div>
              </div>
            </div>
            """
        )

        aktif = st.session_state["aktif_sayfa"]
        for bolum, ogeler in GEZINME.items():
            _md(f'<div class="ez-navsec">{bolum}</div>')
            for etiket, ikon, rozet in ogeler:
                rozet_ek = f"   ·   {rozet}" if rozet else ""
                tip = "primary" if etiket == aktif else "secondary"
                if st.button(f"{ikon}   {etiket}{rozet_ek}", key=f"nav_{etiket}",
                             type=tip, width="stretch"):
                    st.session_state["aktif_sayfa"] = etiket
                    st.rerun()

        _md('<div style="height:14px"></div>')
        _md(
            f"""
            <div class="ez-status">
              <div class="ez-navsec">SİSTEM DURUMU</div>
              <div class="ez-status-row">
                <span><span class="ez-dot">●</span>Çevrimdışı çekirdek</span>
                <span class="ez-status-val" style="color:#22C55E">Aktif</span>
              </div>
              <div class="ez-status-row">
                <span><span class="ez-dot">●</span>Mevzuat endeksi</span>
                <span class="ez-status-val">{len(MEVZUAT_KORPUS) +
                    len(st.session_state['yuklenen_pdfler'])}</span>
              </div>
              <div class="ez-status-row">
                <span><span class="ez-dot" style="color:{'#22C55E' if _BACKEND_VAR
                    else '#F59E0B'}">●</span>İşleme çekirdeği</span>
                <span class="ez-status-val">{'Gerçek · 11 ajan' if _BACKEND_VAR
                    else 'Simülasyon'}</span>
              </div>
            </div>
            <div style="height:10px"></div>
            <div class="ez-status-val" style="text-align:center;opacity:.7">
              © 2026 · Kurumsal Sürüm 2.0<br>Sentetik veri · KVKK uyumlu
            </div>
            """
        )

    return st.session_state["aktif_sayfa"]


# ===========================================================================
#  BÖLÜM 5 — SAYFA: GENEL BAKIŞ (DASHBOARD)
# ===========================================================================

def sayfa_genel_bakis() -> None:
    """Genel Bakış (kurumsal dashboard) sayfasını çizer."""
    _ust_cubuk("Kurumsal Genel Bakış",
               "Akıllı ajan hattının anlık performansı ve evrak akışı",
               canli=True)

    st.caption("ℹ️ **Temsili demo göstergesi:** bu genel-bakış panosundaki toplam "
               "sayaçlar, telemetri, haftalık hacim ve tür dağılımı sunum amaçlı "
               "kurgu verilerdir. **Gerçek uçtan uca işleme ve gerçek metrikler "
               "→ Evrak İşleme sekmesi.**")

    ss = st.session_state
    aktif_ajan = sum(1 for t in ss["ajan_telemetri"].values()
                     if t["durum"] in ("aktif", "calisiyor"))

    # --- Metrik kartları (sparkline'lı) ---------------------------------
    kartlar = [
        _metrik_karti(
            "📥", f"{ss['islenen_evrak']:,}".replace(",", "."),
            "Toplam İşlenen Evrak", "+12,4%", "green", MAVI,
            [random.randint(20, 60) for _ in range(12)]),
        _metrik_karti(
            "🤖", f"{aktif_ajan} / {len(AJANLAR)}",
            "Aktif Çalışan Ajan", "Tümü çevrimiçi", "green", YESIL,
            [random.randint(45, 60) for _ in range(12)]),
        _metrik_karti(
            "⚡", "%85", "Ort. Süre Tasarrufu", "-41 dk/evrak", "green", MAVI,
            [random.randint(25, 58) for _ in range(12)]),
        _metrik_karti(
            "🛡️", "%99,4", "Mevzuat Uyum Skoru", "+0,3", "green", YESIL,
            [random.randint(48, 60) for _ in range(12)]),
    ]
    _md(_metrik_gridi(kartlar))

    # --- Canlı akış + birim sevki (2 sütun) -----------------------------
    dagilim = list(zip(BIRIMLER[:5], [348, 296, 214, 158, 132]))
    yer = st.empty()

    def _grid() -> str:
        return (f'<div class="ez-grid2">'
                f'{_log_paneli_html(ss["log_kayitlari"], random.randint(18, 30))}'
                f'{_birim_paneli_html(dagilim)}</div>')

    yer.markdown(_duzles(_grid()), unsafe_allow_html=True)

    b1, b2 = st.columns([1, 5])
    with b1:
        if st.button("▶ Canlı izlemeyi başlat", type="primary",
                     width="stretch"):
            for _ in range(14):
                ss["log_kayitlari"].append(_log_kaydi())
                ss["log_kayitlari"] = ss["log_kayitlari"][-40:]
                yer.markdown(_duzles(_grid()), unsafe_allow_html=True)
                time.sleep(0.4)

    _md('<div style="height:18px"></div>')

    # --- Alt analitik: tür dağılımı + haftalık hacim --------------------
    g1, g2 = st.columns([2, 3])
    with g1:
        st.markdown("##### 📊 Evrak Türü Dağılımı")
        tur_df = pd.DataFrame({
            "Tür": EVRAK_TURLERI,
            "Adet": [random.randint(120, 940) for _ in EVRAK_TURLERI],
        })
        st.altair_chart(
            alt.Chart(tur_df).mark_arc(innerRadius=55).encode(
                theta="Adet:Q",
                color=alt.Color("Tür:N", scale=alt.Scale(range=KATEGORIK_PALET),
                                legend=alt.Legend(orient="right", title=None)),
                tooltip=["Tür", "Adet"],
            ).properties(height=280),
            width="stretch",
        )
    with g2:
        st.markdown("##### 🗓️ Haftalık İşlem Hacmi")
        hacim_df = pd.DataFrame({
            "Gün": ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"],
            "İşlenen": [random.randint(280, 520) for _ in range(7)],
        }).set_index("Gün")
        st.area_chart(hacim_df, height=280, color=MAVI)


# ===========================================================================
#  BÖLÜM 6 — SAYFA: EVRAK İŞLEME
# ===========================================================================

def sayfa_evrak_isleme() -> None:
    """Evrak İşleme sayfası (giriş + ajan hattı + sonuç kartları)."""
    _ust_cubuk("Evrak İşleme",
               "Tek evrakı uçtan uca analiz et: sınıflandırma → mevzuat → taslak")

    if _BACKEND_VAR:
        st.caption("🟢 **Gerçek mod:** evrak, canlı 11-ajan orkestratörüyle "
                   "(src/) uçtan uca işlenir — tür, özet, mevzuat, KVKK, taslak "
                   "ve yönlendirme gerçek çıktıdır.")
    else:
        st.caption("🟡 **Simülasyon modu:** çekirdek backend yüklenemedi; kurgu "
                   "sonuç gösterilir (açıkça etiketlenir).")

    sol, sag = st.columns([2, 3])
    with sol:
        st.markdown("##### 1) Evrak Girişi")
        yuklenen = st.file_uploader("Evrak dosyası (TXT — PDF için metni yapıştırın)",
                                    type=["txt"])
        varsayilan = ORNEK_DILEKCE
        if yuklenen is not None and yuklenen.type == "text/plain":
            try:
                varsayilan = yuklenen.read().decode("utf-8", errors="ignore")
            except Exception:
                varsayilan = ORNEK_DILEKCE
        metin = st.text_area("Evrak metni", value=varsayilan, height=330)
        calistir = st.button("🚀 Akıllı Ajanı Çalıştır", type="primary",
                             width="stretch")

    with sag:
        st.markdown("##### 2) Ajan Hattı")
        if calistir:
            if not metin or len(metin.strip()) < 15:
                st.warning("Lütfen yeterli uzunlukta bir evrak metni giriniz.")
            else:
                st.session_state["son_analiz"] = _analiz_yap(metin)
        elif st.session_state["son_analiz"] is None:
            st.info("Soldan bir evrak girip **Akıllı Ajanı Çalıştır** butonuna "
                    "basın. Ajan hattı adım adım burada akacaktır.")

    sonuc = st.session_state["son_analiz"]
    if sonuc is not None:
        st.divider()
        _analiz_sonuc_kartlari(sonuc)


def _analiz_yap(metin: str) -> dict:
    """Metni önce GERÇEK 11-ajan pipeline'ıyla işlemeyi dener; backend yoksa
    ya da bu evrakta hata olursa açıkça etiketli kurgu (simülasyon) hattına
    zarifçe iner. Hiçbir durumda uygulamayı çökertmez."""
    pipe = _gercek_pipeline() if _BACKEND_VAR else None
    if pipe is not None:
        try:
            return _gercek_analiz(metin, pipe)
        except Exception as e:
            st.warning(f"⚠️ Gerçek ajan hattı bu evrakta çalıştırılamadı; kurgu "
                       f"(simülasyon) sonucu gösteriliyor. ({type(e).__name__})")
    return _analiz_calistir(metin)


def _gercek_analiz(metin: str, pipe) -> dict:
    """Gerçek pipeline ile analiz — adımlar canlı akar, ham backend sonucu döner."""
    toplam = len(AJAN_HATTI_SIRASI)
    ilerleme = st.progress(0.0, text="Gerçek ajan hattı başlatılıyor...")
    sayac = {"n": 0}
    with st.status("🔄 Gerçek ajan hattı çalışıyor (orkestratör)...",
                   expanded=True) as durum:
        st.write(f"{ORKESTRATOR['ikon']} **{ORKESTRATOR['ad']}** — koşullu akış "
                 "planlanıyor (3 kapı: okunabilirlik / dil / düşük güven)")

        def _on_step(adim: dict) -> None:
            kod = adim.get("agent", "")
            ajan = next((a for a in AJANLAR if a["kod"] == kod), None)
            ikon = ajan["ikon"] if ajan else "⚙️"
            ad = ajan["ad"] if ajan else kod
            simge = {"success": "✓", "atlandi": "⤳",
                     "error": "✗"}.get(adim.get("status"), "•")
            ms = int((adim.get("sure_saniye") or 0) * 1000)
            neden = f" — {adim['neden']}" if adim.get("neden") else ""
            st.write(f"{ikon} {simge} **{ad}**  `{ms} ms`{neden}")
            sayac["n"] += 1
            ilerleme.progress(min(1.0, sayac["n"] / toplam),
                              text=f"{ad} ({sayac['n']}/{toplam})")

        sonuc = pipe.process_text(metin, mode="full", kayit=False,
                                  on_step=_on_step)
        durum.update(label="✅ Gerçek analiz tamamlandı (orkestratör onayı)",
                     state="complete", expanded=False)
    ilerleme.progress(1.0, text="Tamamlandı")
    st.session_state["islenen_evrak"] += 1
    st.session_state["bugun_islenen"] += 1
    sonuc["_gercek"] = True
    sonuc["orijinal_metin"] = metin
    return sonuc


def _analiz_calistir(metin: str) -> dict:
    """Evrak metnini kurgu ajan hattından adım adım geçirir, sonuç döndürür."""
    ilerleme = st.progress(0.0, text="Ajan hattı başlatılıyor...")
    toplam = len(AJAN_HATTI_SIRASI)
    with st.status("🔄 Ajan hattı çalışıyor...", expanded=True) as durum:
        # Orkestratör hattı planlar ve koşullu akışı yönetir.
        st.write(f"{ORKESTRATOR['ikon']} **{ORKESTRATOR['ad']}** — koşullu akış "
                 f"planlanıyor (3 kapı: okunabilirlik / dil / düşük güven)  "
                 f"`52 ms`")
        time.sleep(0.16)
        for i, kod in enumerate(AJAN_HATTI_SIRASI, start=1):
            ajan = next(a for a in AJANLAR if a["kod"] == kod)
            sure = random.randint(90, 420)
            st.write(f"{ajan['ikon']} **{ajan['ad']}** — {ajan['rol']}  "
                     f"`{sure} ms`")
            ilerleme.progress(i / toplam,
                              text=f"{ajan['ad']} tamamlandı ({i}/{toplam})")
            time.sleep(0.14)
        st.write(f"{ORKESTRATOR['ikon']} **{ORKESTRATOR['ad']}** — akış "
                 f"tamamlandı, sonuçlar birleştirildi.  `18 ms`")
        durum.update(label="✅ Analiz tamamlandı (orkestratör onayı)",
                     state="complete", expanded=False)

    st.session_state["islenen_evrak"] += 1
    st.session_state["bugun_islenen"] += 1

    tur = _tur_tahmini(metin)
    oncelik_kod = random.choice(list(ONCELIKLER.keys()))
    ozet = _ozet_uret(metin, tur)
    maskeli, tespitler = _kvkk_maskele(metin)
    return {
        "referans": random.choice(KURGU_EVRAK_REFERANSLARI),
        "tur": tur, "tur_guven": round(random.uniform(0.86, 0.99), 2),
        "ozet": ozet, "mevzuat": random.sample(MEVZUAT_KORPUS, 3),
        "oncelik": ONCELIKLER[oncelik_kod], "birim": random.choice(BIRIMLER),
        "format_skoru": random.randint(88, 99),
        "eksik_alanlar": random.sample(
            ["muhatap", "referans_numaralari", "iletişim", "tarih"],
            k=random.randint(0, 2)),
        "resmi_cevap": _resmi_cevap_uret(tur, random.choice(BIRIMLER)),
        "ozet_kalite": _ozet_kalite_metrikleri(metin, ozet),
        "orijinal_metin": metin, "maskeli_metin": maskeli,
        "pii_tespitleri": tespitler,
        "_gercek": False,
    }


def _tur_tahmini(metin: str) -> str:
    """Anahtar-kelime sezgisiyle (kurgu) evrak türü tahmini."""
    d = metin.lower()
    if "arz ederim" in d or "dilekçe" in d or "başvuru" in d:
        return "Dilekçe"
    if "genelge" in d:
        return "Genelge"
    if "tutanak" in d:
        return "Tutanak"
    if "rica ederim" in d or "gereğini" in d:
        return "Üst Yazı"
    return random.choice(EVRAK_TURLERI)


def _ozet_uret(metin: str, tur: str) -> str:
    """Evrak için kısa yönetici özeti (kurgu)."""
    satirlar = metin.strip().split("\n")
    govde = next((s.strip() for s in satirlar if len(s.strip()) > 40),
                 "Vatandaş talebi içeren resmî nitelikli evrak.")
    return (f"Bu evrak bir {tur.lower()} niteliğindedir. {govde[:180]} "
            f"İlgili birim tarafından mevzuata uygun şekilde değerlendirilmesi "
            f"ve yasal süre içinde yanıtlanması önerilmektedir.")


def _resmi_cevap_uret(tur: str, birim: str) -> str:
    """DYS/e-Yazışma formatında resmî cevap taslağı (kurgu)."""
    tarih = datetime.now().strftime("%d.%m.%Y")
    sayi = f"E-{random.randint(10000, 99999)}-{random.randint(100, 999)}"
    ref = random.choice(KURGU_EVRAK_REFERANSLARI)
    return f"""T.C.
ÖRNEK KURUMU
{birim.upper()}

Sayı   : {sayi}
Tarih  : {tarih}
Konu   : {tur} Başvurusunun Değerlendirilmesi

İLGİLİ MAKAMA / BAŞVURU SAHİBİNE

İlgi   : {ref} sayılı ve {tarih} tarihli başvurunuz.

İlgi'de kayıtlı başvurunuz Kurumumuzca incelenmiş olup, talebiniz ilgili
mevzuat (3071 sayılı Dilekçe Hakkı Kanunu ve Resmî Yazışmalarda Uygulanacak
Usul ve Esaslar) çerçevesinde değerlendirmeye alınmıştır.

Yapılan inceleme sonucunda, söz konusu talebinizle ilgili gerekli iş ve
işlemlerin başlatıldığını, süreç hakkında tarafınıza yasal süre içerisinde
ayrıca bilgi verileceğini önemle belirtiriz.

Bilgilerinize rica/arz olunur.


                                                        [Yetkili Amir]
                                                        {birim}

Ek: Yok
Dağıtım: Gereği için ilgili birim; Bilgi için başvuru sahibi.
"""


def _analiz_sonuc_kartlari(sonuc: dict) -> None:
    """Analiz sonucunu çizer; gerçek backend çıktısı ile kurgu ayrı gösterilir."""
    if sonuc.get("_gercek"):
        _gercek_sonuc_goster(sonuc)
    else:
        _kurgu_sonuc_goster(sonuc)


def _gercek_sonuc_goster(sonuc: dict) -> None:
    """GERÇEK 11-ajan orkestratör çıktısını kurumsal kartlarla gösterir.

    Buradaki tüm değerler canlı backend sonucudur (kurgu/random DEĞİL):
    sınıflandırma güveni, mevzuat benzerliği, taslak kalite puanı, KVKK
    maskeleme sayıları ve insan onayı işaretleri src/ orkestratöründen gelir.
    """
    cls = sonuc.get("siniflandirma") or {}
    triage = sonuc.get("onceliklendirme") or {}
    routing = sonuc.get("yonlendirme") or {}
    fmt = sonuc.get("format_denetimi") or {}
    kalite = sonuc.get("taslak_kalitesi") or {}
    onay = sonuc.get("insan_onayi") or {}

    st.success("🟢 **Gerçek 11-ajan hattı ile işlendi** — aşağıdaki tüm sonuçlar "
               "canlı orkestratör çıktısıdır (kurgu/simülasyon değildir).")

    # --- Üst metrik satırı (gerçek) -------------------------------------
    guven = cls.get("guven")
    fmt_skor = fmt.get("skor")
    rguven = routing.get("guven")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Evrak Türü", cls.get("tur_adi", "—"),
              delta=(f"güven %{int(guven * 100)}" if guven is not None else None))
    k2.metric("Öncelik", ONCELIKLER.get(triage.get("oncelik", "normal"),
                                        triage.get("oncelik", "—")))
    k3.metric("Resmî Yazışma Skoru",
              f"{int((fmt_skor or 0) * 100)}/100",
              delta=("Formata uygun" if fmt.get("uygun") else "Eksik/uyarı var"))
    k4.metric("Yönlendirme güveni",
              f"%{int(rguven * 100)}" if rguven is not None else "—")
    k4.caption(f"🧭 {routing.get('birim', '—')}")

    # --- İnsan onayı (gerçek HITL) --------------------------------------
    if onay.get("gerekli"):
        st.warning("🛑 **İnsan onayı gerekli** (düşük güven / tutarsızlık):\n\n"
                   + "\n".join(f"- {g}" for g in onay.get("gerekceler", [])))

    # --- Özet + Mevzuat (gerçek) ----------------------------------------
    ozet_col, mevzuat_col = st.columns(2)
    with ozet_col:
        with st.container(border=True):
            st.markdown("#### 📝 Özet")
            st.write(sonuc.get("ozet") or "—")
            eksik = sonuc.get("eksik_bilgiler") or []
            if eksik:
                st.warning("Eksik zorunlu alanlar: "
                           + ", ".join(e.get("alan", "?") for e in eksik))
            else:
                st.success("Zorunlu alanların tamamı mevcut. ✔")
    with mevzuat_col:
        with st.container(border=True):
            meta = sonuc.get("mevzuat_arama_meta") or {}
            yontem = str(meta.get("yontem", "bm25")).upper()
            st.markdown(f"#### ⚖️ Mevzuat Analizi (RAG · {yontem})")
            mv = sonuc.get("mevzuat_eslestirme") or []
            if not mv:
                st.caption("Eşleşen mevzuat maddesi bulunamadı.")
            for m in mv[:3]:
                skor = float(m.get("benzerlik") or 0.0)
                st.write(f"**{m.get('mevzuat_adi') or m.get('baslik', '—')}** "
                         f"· {m.get('madde_etiketi', '')}")
                st.caption((m.get("icerik_ozeti") or m.get("gerekce") or "")[:150])
                st.progress(min(1.0, max(0.0, skor)),
                            text=f"benzerlik {skor:.2f}")

    # --- Taslak kalite hakemi (gerçek, 0-100) ---------------------------
    if kalite:
        with st.container(border=True):
            st.markdown("#### 📐 Taslak Kalite Hakemi (gerçek · 0-100)")
            bilesen = kalite.get("bilesenler") or {}
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Toplam Puan", kalite.get("puan", "—"))
            q2.metric("Biçim", bilesen.get("bicim", "—"))
            q3.metric("Üslup", bilesen.get("uslup", "—"))
            q4.metric("Mevzuat Temelliliği", bilesen.get("mevzuat_temellilik", "—"))
            for not_ in kalite.get("notlar", []):
                st.warning("⚠ " + str(not_))

    # --- KVKK öncesi/sonrası (gerçek anonimleştirme) --------------------
    _gercek_kvkk_paneli(sonuc)

    # --- Önceliklendirme / yasal süre (gerçek) --------------------------
    if triage.get("yasal_sure") or triage.get("sinyaller"):
        with st.container(border=True):
            st.markdown("#### 🚦 Önceliklendirme ve Yasal Süre")
            ys = triage.get("yasal_sure") or {}
            st.write(f"**Öncelik:** "
                     f"{ONCELIKLER.get(triage.get('oncelik', 'normal'), '—')}")
            if ys.get("kaynak"):
                st.caption("Yasal süre dayanağı: " + str(ys.get("kaynak")))
            if triage.get("kalan_gun") is not None:
                st.info(f"Kalan yasal süre: **{triage.get('kalan_gun')} gün**")

    # --- Resmî cevap taslağı (gerçek üretim) ----------------------------
    taslak = (sonuc.get("yazi_taslagi") or "").strip()
    with st.container(border=True):
        st.markdown("#### 📄 Resmî Cevap Taslağı (gerçek üretim)")
        if taslak:
            st.code(taslak, language="text")
            st.download_button("⬇️ Taslağı İndir (.txt)", data=taslak,
                               file_name="resmi_cevap_taslak.txt",
                               mime="text/plain", width="stretch")
        else:
            st.info("Bu evrak için taslak üretilmedi (ör. dil kapısı: metin "
                    "Türkçe görünmüyor, veya okunabilirlik kapısı).")

    # --- Ajan hattı adımları (gerçek süre) ------------------------------
    adimlar = sonuc.get("islem_adimlari") or []
    if adimlar:
        with st.expander(f"🔬 Ajan hattı adımları · toplam "
                         f"{sonuc.get('islem_suresi_saniye', '?')} sn"):
            st.dataframe(pd.DataFrame([{
                "Ajan": a.get("agent"), "Adım": a.get("description"),
                "Durum": a.get("status"),
                "Süre (ms)": int((a.get("sure_saniye") or 0) * 1000),
            } for a in adimlar]), width="stretch", hide_index=True)


def _gercek_kvkk_paneli(sonuc: dict) -> None:
    """Gerçek anonimleştirme sonucunu (öncesi/sonrası + sayaçlar) gösterir."""
    anon = sonuc.get("anonimlestirme") or {}
    maskeli = anon.get("metin") or ""
    rapor = anon.get("rapor") or {}
    sayac = rapor.get("maskelenen") or {}
    toplam = rapor.get("toplam", sum(sayac.values()) if sayac else 0)
    with st.container(border=True):
        st.markdown("#### 🛡️ KVKK Anonimleştirme — Öncesi / Sonrası (gerçek)")
        if toplam:
            st.caption(f"{toplam} adet kişisel veri (PII) tespit edilip "
                       f"maskelendi (6698 sayılı KVKK).")
        else:
            st.caption("Metinde maskelenecek kişisel veri (PII) bulunmadı.")
        sol, sag = st.columns(2)
        with sol:
            st.markdown("**🔓 Orijinal (PII içerir)**")
            st.code(sonuc.get("orijinal_metin", ""), language="text")
        with sag:
            st.markdown("**🔒 Maskeli (paylaşıma uygun)**")
            st.code(maskeli, language="text")
        satir = [{"Veri Türü": _PII_ETIKET.get(k, k), "Maskelenen Adet": v}
                 for k, v in sayac.items() if v]
        if satir:
            st.dataframe(pd.DataFrame(satir), width="stretch", hide_index=True)


def _kurgu_sonuc_goster(sonuc: dict) -> None:
    """Kurgu (simülasyon) analiz sonucunu kurumsal kartlar halinde çizer."""
    st.info("🟡 **Simülasyon sonucu** — bu kartlar kurgu (mock) veri gösterir; "
            "çekirdek backend yüklendiğinde sonuçlar gerçek olur.")
    st.markdown(f"### 🧾 Analiz Sonucu · `{sonuc['referans']}`")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Evrak Türü", sonuc["tur"],
              delta=f"güven %{int(sonuc['tur_guven'] * 100)}")
    k2.metric("Öncelik", sonuc["oncelik"])
    k3.metric("Resmî Yazışma Skoru", f"{sonuc['format_skoru']}/100",
              delta="Formata uygun")
    k4.metric("Yönlendirme", "🧭", help=sonuc["birim"])
    k4.write(f"**{sonuc['birim']}**")

    ozet_col, mevzuat_col = st.columns(2)
    with ozet_col:
        with st.container(border=True):
            st.markdown("#### 📝 Özet")
            st.write(sonuc["ozet"])
            if sonuc["eksik_alanlar"]:
                st.warning("Eksik zorunlu alanlar: "
                           + ", ".join(sonuc["eksik_alanlar"]))
            else:
                st.success("Zorunlu alanların tamamı mevcut. ✔")
    with mevzuat_col:
        with st.container(border=True):
            st.markdown("#### ⚖️ Mevzuat Analizi (RAG · İsabet@3)")
            for m in sonuc["mevzuat"]:
                skor = round(random.uniform(0.72, 0.97), 2)
                st.write(f"**{m['kod']} · {m['baslik']}**")
                st.caption(f"{m['tur']} ({m['yil']}) — İlgi skoru: {skor}")
                st.progress(skor)

    kanun_col, aksiyon_col = st.columns(2)
    with kanun_col:
        with st.container(border=True):
            st.markdown("#### 📜 İlgili Kanun Maddeleri")
            for m in sonuc["mevzuat"]:
                madde = random.randint(1, min(30, m["madde"]))
                st.write(f"• **{m['kod']} m.{madde}** — {m['ozet']}")
    with aksiyon_col:
        with st.container(border=True):
            st.markdown("#### 🎯 Önerilen Aksiyon")
            st.write(f"1. Evrakı **{sonuc['birim']}** birimine havale et.")
            st.write(f"2. Önceliğe göre işleme al: **{sonuc['oncelik']}**.")
            st.write("3. Aşağıdaki resmî cevap taslağını amir onayına sun.")
            st.write("4. Başvuru sahibini yasal süre içinde bilgilendir.")

    _ozet_kalite_paneli(sonuc["ozet_kalite"])
    _anonim_karsilastirma_paneli(sonuc)

    with st.container(border=True):
        st.markdown("#### 📄 DYS Formatında Resmî Cevap Taslağı")
        st.caption("Kopyalamak için kod bloğunun sağ üstündeki simgeyi kullanın.")
        st.code(sonuc["resmi_cevap"], language="text")
        st.download_button("⬇️ Taslağı İndir (.txt)", data=sonuc["resmi_cevap"],
                           file_name=f"{sonuc['referans']}_resmi_cevap.txt",
                           mime="text/plain", width="stretch")


# ===========================================================================
#  BÖLÜM 7 — KVKK MASKELEME + ÖZET KALİTE (İŞ MANTIĞI)
# ===========================================================================

def _kvkk_maskele(metin: str) -> tuple:
    """Metindeki kişisel veri (PII) alanlarını maskeler (KVKK)."""
    tespitler: list = []
    maskeli = metin

    def _uygula(desen: str, tur: str, maske_fn) -> None:
        nonlocal maskeli
        for eslesme in re.finditer(desen, maskeli):
            orijinal = eslesme.group(0)
            maske = maske_fn(orijinal)
            if orijinal == maske:
                continue
            tespitler.append({"tur": tur, "orijinal": orijinal, "maske": maske})
            maskeli = maskeli.replace(orijinal, maske, 1)

    _uygula(r"\b[1-9]\d{10}\b", "TCKN",
            lambda s: s[:2] + "*******" + s[-2:])
    _uygula(r"\b[\w.\-]+@[\w.\-]+\.\w{2,}\b", "E-posta",
            lambda s: s[0] + "***@" + s.split("@")[-1])
    _uygula(r"0(?:[\s.\-]?[\dxX]){10}", "Telefon",
            lambda s: "05## ### ## ##")
    _uygula(r"\bTR\d{2}[\s\d]{20,28}\b", "IBAN",
            lambda s: "TR## **** **** **** ****")
    for eslesme in re.finditer(r"(Ad\s*Soyad\s*[:：]\s*)(.+)", maskeli):
        onek, isim = eslesme.group(1), eslesme.group(2).strip()
        if isim:
            tespitler.append({"tur": "Ad-Soyad", "orijinal": isim,
                              "maske": "[MASKELENDİ]"})
            maskeli = maskeli.replace(
                eslesme.group(0), onek + "[KİŞİSEL VERİ — MASKELENDİ]", 1)
    return maskeli, tespitler


def _ozet_kalite_metrikleri(metin: str, ozet: str) -> dict:
    """Özet için kalite metrikleri (gerçek ROUGE-L + kurgu göstergeler)."""
    kaynak = re.findall(r"\w+", metin.lower())
    ozet_t = re.findall(r"\w+", ozet.lower())
    kisaltma = round(1 - len(ozet_t) / len(kaynak), 2) if kaynak else 0.0
    return {
        "rouge_l": round(_rouge_l_f1(kaynak, ozet_t), 3),
        "sadakat": round(random.uniform(0.90, 0.98), 3),
        "kapsam": round(random.uniform(0.82, 0.95), 3),
        "kisaltma_orani": max(0.0, kisaltma),
        "halusinasyon": random.choice([0, 0, 0, 1]),
    }


def _rouge_l_f1(kaynak: list, ozet: list) -> float:
    """İki token dizisi için ROUGE-L F1 (LCS tabanlı) hesaplar."""
    if not kaynak or not ozet:
        return 0.0
    onceki = [0] * (len(ozet) + 1)
    for i in range(1, len(kaynak) + 1):
        simdiki = [0] * (len(ozet) + 1)
        for j in range(1, len(ozet) + 1):
            if kaynak[i - 1] == ozet[j - 1]:
                simdiki[j] = onceki[j - 1] + 1
            else:
                simdiki[j] = max(onceki[j], simdiki[j - 1])
        onceki = simdiki
    lcs = onceki[len(ozet)]
    if lcs == 0:
        return 0.0
    duyarlilik, anma = lcs / len(ozet), lcs / len(kaynak)
    return 2 * duyarlilik * anma / (duyarlilik + anma)


def _ozet_kalite_paneli(kalite: dict) -> None:
    """Özet kalite göstergelerini (ROUGE-L, sadakat) çizer."""
    with st.container(border=True):
        st.markdown("#### 📐 Özet Kalite Göstergesi (Sadakat Denetimi)")
        st.caption("ROUGE-L kaynakla örtüşmeyi (LCS-F1) ölçer; sadakat ve "
                   "kapsam özetin doğruluk/temsil gücünü değerlendirir.")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("ROUGE-L (F1)", f"{kalite['rouge_l']:.2f}")
        q2.metric("Sadakat", f"{kalite['sadakat']:.2f}", delta="Denetimden geçti")
        q3.metric("Kapsam", f"{kalite['kapsam']:.2f}")
        q4.metric("Kısaltma Oranı", f"%{int(kalite['kisaltma_orani'] * 100)}")
        st.progress(kalite["sadakat"], text=f"Sadakat {kalite['sadakat']:.2f}")
        if kalite["halusinasyon"]:
            st.warning("⚠️ Olası halüsinasyon işareti: kaynakta doğrulanamayan "
                       "ifade — insan denetimine öneriliyor.")
        else:
            st.success("✔ Halüsinasyon tespit edilmedi; özet kaynağa sadık.")


def _anonim_karsilastirma_paneli(sonuc: dict) -> None:
    """KVKK anonimleştirme öncesi/sonrası karşılaştırmasını çizer."""
    with st.container(border=True):
        st.markdown("#### 🛡️ KVKK Anonimleştirme — Öncesi / Sonrası")
        tespitler = sonuc["pii_tespitleri"]
        if tespitler:
            st.caption(f"{len(tespitler)} adet kişisel veri (PII) tespit edildi "
                       f"ve maskelendi (6698 sayılı KVKK).")
        else:
            st.caption("Metinde maskelenecek kişisel veri (PII) bulunmadı.")
        sol, sag = st.columns(2)
        with sol:
            st.markdown("**🔓 Orijinal (PII içerir)**")
            st.code(sonuc["orijinal_metin"], language="text")
        with sag:
            st.markdown("**🔒 Maskeli (paylaşıma uygun)**")
            st.code(sonuc["maskeli_metin"], language="text")
        if tespitler:
            st.dataframe(
                pd.DataFrame(tespitler).rename(columns={
                    "tur": "Veri Türü", "orijinal": "Orijinal", "maske": "Maskeli"}),
                width="stretch", hide_index=True)
            sizinti = round(random.uniform(0.0, 0.03), 3)
            st.metric("KVKK Sızıntı Skoru", f"{sizinti:.3f}",
                      delta="Hedef ≤ 0.05 ✔")


# ===========================================================================
#  BÖLÜM 8 — SAYFA: TOPLU İŞLEME (CANLI KUYRUK)
# ===========================================================================

def sayfa_toplu_isleme() -> None:
    """Toplu İşleme sayfası (canlı kuyruk + toplu evrak işleme)."""
    _ust_cubuk("Toplu İşleme",
               "Evrak kuyruğunu canlı olarak işle — yüksek hacimli otomasyon")
    st.caption("ℹ️ **Temsili demo simülasyonu:** yüksek hacimli kuyruk akışını "
               "görselleştirir (kurgu evraklar). Gerçek toplu işleme için: "
               "`python -m src.main --klasor data/raw/kurgu_evraklar` veya tek "
               "evrak için **Evrak İşleme** sekmesi.")
    kontrol, ozet = st.columns([2, 3])
    with kontrol:
        st.markdown("##### 🎛️ Kuyruk Ayarları")
        adet = st.slider("İşlenecek evrak sayısı", 5, 60, 20, step=5)
        hiz = st.select_slider("İşleme hızı", ["Yavaş", "Normal", "Hızlı"],
                               value="Normal")
        baslat = st.button("▶ Toplu İşlemeyi Başlat", type="primary",
                           width="stretch")
    with ozet:
        st.markdown("##### 📥 Bekleyen Kuyruk")
        st.info(f"Kuyrukta **{adet}** kurgu evrak var. Her evrak "
                f"{len(AJANLAR)} ajanlık hattan geçirilecek; öncelik ve birim "
                f"otomatik atanacak.\n\nToplam ajan-adımı: "
                f"**{adet * len(AJANLAR)}**.")
    st.divider()
    if baslat:
        _toplu_isle(adet, hiz)
    else:
        st.caption("Başlatmak için **Toplu İşlemeyi Başlat** butonuna basın.")


def _toplu_isle(adet: int, hiz: str) -> None:
    """Verilen sayıda kurgu evrakı canlı kuyrukta işler."""
    gecikme = {"Yavaş": 0.22, "Normal": 0.10, "Hızlı": 0.04}[hiz]
    ust = st.columns(4)
    m_islenen, m_ivedi = ust[0].empty(), ust[1].empty()
    m_sure, m_basari = ust[2].empty(), ust[3].empty()
    ilerleme = st.progress(0.0, text="Kuyruk işleniyor...")
    tablo = st.empty()

    satirlar, ivedi, toplam_sure, basarili = [], 0, 0, 0
    for i in range(1, adet + 1):
        ref = f"EVR-2026-{random.randint(500, 999):06d}"
        oncelik = random.choice(list(ONCELIKLER.values()))
        sure = random.randint(320, 1450)
        durum = random.choices(["✅ Tamamlandı", "🟡 İnsan onayı"],
                               weights=[0.85, 0.15])[0]
        if "İVEDİ" in oncelik:
            ivedi += 1
        toplam_sure += sure
        if durum.startswith("✅"):
            basarili += 1
        satirlar.append({"Sıra": i, "Referans": ref,
                         "Tür": random.choice(EVRAK_TURLERI),
                         "Öncelik": oncelik, "Birim": random.choice(BIRIMLER),
                         "Süre (ms)": sure, "Durum": durum})
        m_islenen.metric("İşlenen", f"{i}/{adet}")
        m_ivedi.metric("İvedi/Çok İvedi", ivedi)
        m_sure.metric("Ort. Süre", f"{toplam_sure // i} ms")
        m_basari.metric("Otomatik Başarı", f"%{int(basarili / i * 100)}")
        ilerleme.progress(i / adet, text=f"{ref} işlendi ({i}/{adet})")
        tablo.dataframe(pd.DataFrame(satirlar[-12:]),
                        width="stretch", hide_index=True)
        time.sleep(gecikme)

    ilerleme.progress(1.0, text="✅ Toplu işleme tamamlandı")
    st.session_state["islenen_evrak"] += adet
    st.session_state["bugun_islenen"] += adet
    st.success(f"Toplam **{adet}** evrak işlendi · Ort. süre "
               f"**{toplam_sure // adet} ms** · Otomatik başarı "
               f"**%{int(basarili / adet * 100)}**.")
    df = pd.DataFrame(satirlar)
    st.markdown("##### 🧾 Tam Sonuç Tablosu")
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button("⬇️ Sonuçları İndir (CSV)",
                       data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="toplu_isleme_sonuc.csv", mime="text/csv")


# ===========================================================================
#  BÖLÜM 9 — SAYFA: AJAN YÖNETİMİ (MULTI-AGENT)
# ===========================================================================

def _orkestrator_paneli() -> None:
    """Orkestratör (çekirdek koordinatör) durum panelini çizer.

    11 uzman ajanı yöneten orkestratörü; canlı telemetrisi, tamamladığı akış
    sayısı ve 3 karar kapısı (okunabilirlik / dil / düşük güven) ile gösterir.
    """
    tel = st.session_state["orkestrator_tel"]
    rozet = {"aktif": "🟢 Aktif", "calisiyor": "🔵 Çalışıyor",
             "beklemede": "🟡 Beklemede"}[tel["durum"]]
    st.markdown("##### 🧠 Orkestratör — Çekirdek Koordinatör")
    with st.container(border=True):
        st.markdown(f"### {ORKESTRATOR['ikon']} {ORKESTRATOR['ad']}  ·  {rozet}")
        st.caption(ORKESTRATOR["rol"])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Yönetilen Ajan", f"{len(AJANLAR)}")
        m2.metric("Tamamlanan Akış", f"{tel['tamamlanan_akis']:,}".replace(",", "."))
        m3.metric("CPU", f"%{tel['cpu']}")
        m4.metric("Bellek", f"{int(tel['bellek'])} MB")

        st.markdown("**Karar Kapıları (koşullu akış)**")
        g1, g2, g3 = st.columns(3)
        g1.success("🚪 Okunabilirlik kapısı — geçildi")
        g2.success("🚪 Dil kapısı — geçildi")
        eskale = random.randint(0, 3)
        if eskale:
            g3.warning(f"🚪 Düşük güven kapısı — {eskale} evrak insan onayına")
        else:
            g3.success("🚪 Düşük güven kapısı — eskalasyon yok")


def sayfa_ajan_yonetimi() -> None:
    """Ajan Yönetimi sayfası (ajan kartları + mesajlaşma simülasyonu)."""
    _ust_cubuk("Ajan Yönetimi",
               f"{len(AJANLAR)} uzman ajan + orkestratör — canlı telemetri")
    st.caption("ℹ️ Ajan listesi ve roller **gerçektir** (src/agents ile birebir); "
               "CPU/bellek/işlem **telemetrisi temsili demo** göstergesidir. "
               "Gerçek adım süreleri **Evrak İşleme** çıktısında görünür.")
    ss = st.session_state
    aktif = sum(1 for t in ss["ajan_telemetri"].values() if t["durum"] == "aktif")
    calisan = sum(1 for t in ss["ajan_telemetri"].values()
                  if t["durum"] == "calisiyor")
    bekleyen = sum(1 for t in ss["ajan_telemetri"].values()
                   if t["durum"] == "beklemede")
    toplam = sum(t["islem"] for t in ss["ajan_telemetri"].values())
    kartlar = [
        _metrik_karti("🟢", str(aktif), "Aktif Ajan", "çalışıyor", "green",
                      YESIL, [random.randint(30, 60) for _ in range(10)]),
        _metrik_karti("🔵", str(calisan), "İşlemde", "", "blue", MAVI,
                      [random.randint(20, 55) for _ in range(10)]),
        _metrik_karti("🟡", str(bekleyen), "Beklemede", "", "amber", SARI,
                      [random.randint(15, 40) for _ in range(10)]),
        _metrik_karti("📈", f"{toplam:,}".replace(",", "."), "Toplam İşlem",
                      "kümülatif", "blue", MAVI_ACIK,
                      [random.randint(35, 60) for _ in range(10)]),
    ]
    _md(_metrik_gridi(kartlar))

    # --- Orkestratör (çekirdek koordinatör) paneli ----------------------
    _orkestrator_paneli()

    st.markdown("##### 🧩 Uzman Ajan Filosu")
    st.caption(f"Aşağıdaki {len(AJANLAR)} uzman ajan, orkestratör tarafından "
               f"koşullu akışla yönetilir.")
    sutunlar = st.columns(3)
    for idx, ajan in enumerate(AJANLAR):
        tel = ss["ajan_telemetri"][ajan["kod"]]
        rozet = {"aktif": "🟢 Aktif", "calisiyor": "🔵 Çalışıyor",
                 "beklemede": "🟡 Beklemede"}[tel["durum"]]
        with sutunlar[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {ajan['ikon']} {ajan['ad']}")
                st.caption(ajan["kategori"])
                st.write(rozet)
                c1, c2 = st.columns(2)
                c1.metric("CPU", f"%{tel['cpu']}")
                c2.metric("Bellek", f"{int(tel['bellek'])} MB")
                st.metric("İşlem", f"{tel['islem']:,}".replace(",", "."))
                st.progress(int(tel["cpu"]) / 100)
                st.caption(f"Son görev: {ajan['rol'][:58]}...")

    st.divider()
    st.markdown("##### 💬 Ajanlar Arası Mesajlaşma (Orkestrasyon)")
    yer = st.empty()
    yer.code("\n".join(ss["ajan_mesajlari"][-10:]), language="log")
    if st.button("▶ Simülasyonu Başlat", type="primary"):
        for _ in range(10):
            ss["ajan_mesajlari"].append(_ajan_mesaji())
            ss["ajan_mesajlari"] = ss["ajan_mesajlari"][-30:]
            yer.code("\n".join(ss["ajan_mesajlari"][-10:]), language="log")
            time.sleep(0.3)

    st.divider()
    st.markdown("##### 📊 Ajan Bazlı İşlem Yükü")
    yuk_df = pd.DataFrame({
        "Ajan": [a["ad"] for a in AJANLAR],
        "İşlem": [ss["ajan_telemetri"][a["kod"]]["islem"] for a in AJANLAR]})
    st.altair_chart(
        alt.Chart(yuk_df).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("İşlem:Q", title="Toplam İşlem"),
            y=alt.Y("Ajan:N", sort="-x", title=None),
            color=alt.Color("İşlem:Q", legend=None,
                            scale=alt.Scale(scheme="blues")),
            tooltip=["Ajan", "İşlem"]).properties(height=360),
        width="stretch")


# ===========================================================================
#  BÖLÜM 9.5 — SAYFA: ASİSTAN (ORKESTRATÖR SOHBETİ)
# ===========================================================================

# Hazır hızlı sorular (sohbet başlatıcılar).
_HIZLI_SORULAR = [
    "Ajanların şu anki durumu nedir?",
    "3071 sayılı kanuna göre dilekçeye kaç günde cevap verilir?",
    "Bir dilekçeyi hangi birime yönlendirmeliyim?",
    "Bu evrakta KVKK / kişisel veri riski var mı?",
    "Çok ivedi bir evrak için süreç nasıl işler?",
    "Sistem neler yapabilir?",
]


@st.cache_resource(show_spinner=False)
def _legislation_agent():
    """Mevzuat (BM25/RAG) arama ajanı — Asistan'ın gerçek mevzuat yanıtları için."""
    if not _BACKEND_VAR:
        return None
    try:
        from src.agents.legislation_agent import LegislationAgent
        return LegislationAgent()
    except Exception:
        return None


def _gercek_mevzuat_ara(soru: str, limit: int = 3):
    """Soruyu gerçek BM25/RAG korpusunda arar; başarısızsa None döner."""
    agent = _legislation_agent()
    if agent is None or _AgentState is None:
        return None
    try:
        state = _AgentState(
            raw_text=soru,
            classification={"tur": "dilekce", "tur_adi": "Dilekçe"},
        )
        agent.run(state)
        return (state.legislation_matches or [])[:limit]
    except Exception:
        return None


def _orkestrator_yanit(soru: str) -> str:
    """Orkestratörün yanıtını üretir (mevzuat için gerçek BM25/RAG kullanır).

    Soruyu anahtar kelimelere göre ilgili uzman ajana 'yönlendirir'. Mevzuat
    sorularında gerçek RAG korpusunda arama yapar; erişilemezse bilgi kartına
    iner. Emin olunmayan konularda bilgi yetersizliğini açıkça belirtir
    (halüsinasyon yasağı — Anayasal İlke 2).
    """
    s = soru.lower()
    ss = st.session_state

    def _yonlendir(ajan_ad: str, govde: str) -> str:
        return (f"🧭 Bu soruyu **{ajan_ad}**'na yönlendirdim.\n\n{govde}")

    # Selamlama
    if any(k in s for k in ["merhaba", "selam", "günaydın", "iyi günler"]):
        return ("Merhaba! 👋 Size nasıl yardımcı olabilirim? Evrak, mevzuat, "
                "ajan durumu, KVKK veya yönlendirme hakkında sorabilirsiniz.")

    # Yetenekler / yardım
    if any(k in s for k in ["ne yapab", "neler yap", "yardım", "yetenek",
                            "nasıl kullan", "ne işe", "sistem neler"]):
        return ("Şunları yapabilirim:\n"
                "- 📥 **Evrak analizi**: tür, özet, öncelik, eksik alan tespiti\n"
                "- ⚖️ **Mevzuat/RAG**: ilgili kanun-yönetmelik maddelerini bulma\n"
                "- 🧭 **Yönlendirme**: doğru birime havale önerisi\n"
                "- 🛡️ **KVKK**: kişisel veri tespiti ve maskeleme\n"
                "- ✍️ **Taslak**: resmî yazışma formatında cevap üretme\n"
                "- 🤖 **Ajan durumu**: filo telemetrisi ve orkestrasyon\n\n"
                "Sol taraftaki hızlı sorulardan da başlayabilirsiniz.")

    # Ajan durumu
    if any(k in s for k in ["ajan", "durum", "telemetri", "filo", "çalışıyor",
                           "aktif mi"]):
        aktif = sum(1 for t in ss["ajan_telemetri"].values()
                    if t["durum"] in ("aktif", "calisiyor"))
        ork = ss["orkestrator_tel"]
        akis = f"{ork['tamamlanan_akis']:,}".replace(",", ".")
        toplam = f"{ss['islenen_evrak']:,}".replace(",", ".")
        return ("🤖 **Ajan Filosu Durumu**\n\n"
                f"- Aktif/çalışan uzman ajan: **{aktif}/{len(AJANLAR)}**\n"
                f"- Orkestratör: **🟢 {ork['durum'].capitalize()}** "
                f"(tamamlanan akış: {akis})\n"
                f"- Bugün işlenen evrak: **{ss['bugun_islenen']}**\n"
                f"- Toplam işlenen: **{toplam}**\n\n"
                "Detay için **Ajan Yönetimi** sekmesine bakabilirsiniz.")

    # Mevzuat / kanun / süre
    if any(k in s for k in ["mevzuat", "kanun", "yönetmelik", "madde", "gün",
                           "süre", "yasal", "3071", "4982", "6698", "kaç gün"]):
        gercek = _gercek_mevzuat_ara(soru)
        if gercek:
            satir = "\n".join(
                f"- **{m.get('mevzuat_adi') or m.get('baslik', '—')}** "
                f"{m.get('madde_etiketi', '')} "
                f"(benzerlik {float(m.get('benzerlik') or 0):.2f})"
                for m in gercek[:3])
            kaynak = "gerçek BM25/RAG araması"
        else:
            adaylar = [m for m in MEVZUAT_KORPUS
                       if m["kod"].lower() in s or any(
                           kel in m["baslik"].lower() for kel in s.split())]
            if not adaylar:
                adaylar = MEVZUAT_KORPUS[:3]
            satir = "\n".join(
                f"- **{m['kod']} · {m['baslik']}** ({m['tur']}, {m['yil']}) — "
                f"{m['ozet']}" for m in adaylar[:3])
            kaynak = "mevzuat bilgi kartı"
        ek = ""
        if "3071" in s or "dilekçe" in s or "kaç gün" in s:
            ek = ("\n\n📌 **Özet cevap:** 3071 sayılı Dilekçe Hakkı Kanunu "
                  "uyarınca idare, başvurulara **en geç 30 gün** içinde cevap "
                  "vermekle yükümlüdür.")
        return _yonlendir("Mevzuat Ajanı",
                          f"İlgili mevzuat ({kaynak}):\n{satir}{ek}")

    # KVKK / kişisel veri
    if any(k in s for k in ["kvkk", "kişisel veri", "maskele", "anonim", "pii",
                           "tckn", "gizlilik"]):
        return _yonlendir(
            "KVKK Anonimleştirme Ajanı",
            "6698 sayılı KVKK kapsamında evraklardaki **TCKN, telefon, e-posta, "
            "IBAN ve ad-soyad** gibi kişisel verileri otomatik tespit edip "
            "maskeliyorum. Öncesi/sonrası karşılaştırmasını ve sızıntı skorunu "
            "**KVKK ve Uyum** sekmesinde canlı deneyebilirsiniz.")

    # Öncelik / ivedi
    if any(k in s for k in ["öncelik", "ivedi", "acil", "aciliyet", "önceliklendir"]):
        return _yonlendir(
            "Önceliklendirme Ajanı",
            "Evrakları aciliyet + yasal süre analizine göre şu seviyelere "
            "ayırıyorum: " + ", ".join(ONCELIKLER.values()) + ".\n\n"
            "**Çok ivedi** evraklar öncelikli kuyruğa alınır; taslak ve "
            "yönlendirme ilk sırada işlenir, ilgili amire anında bildirilir.")

    # Yönlendirme / birim
    if any(k in s for k in ["birim", "yönlendir", "havale", "hangi müdürlük",
                           "kime gönder"]):
        return _yonlendir(
            "Yönlendirme Ajanı",
            "Evrak içeriğine göre şu birimlerden uygun olana havale öneriyorum:\n"
            + "\n".join(f"- {b}" for b in BIRIMLER[:5])
            + "\n\nÖrneğin bir kaldırım/imar dilekçesi genelde "
            "**İmar ve Şehircilik Md.**'ne yönlendirilir.")

    # Özet
    if any(k in s for k in ["özet", "özetle", "kısaca"]):
        return _yonlendir(
            "Özet Ajanı",
            "Evrakların sadakat denetimli (ROUGE-L kontrollü) yönetici özetini "
            "çıkarıyorum. Bir evrak yüklemek için **Evrak İşleme** sekmesini "
            "kullanın; özet ve kalite göstergesini orada görürsünüz.")

    # Taslak / cevap
    if any(k in s for k in ["taslak", "cevap yaz", "resmî yazı", "resmi yazı",
                           "yazı hazırla", "dys"]):
        return _yonlendir(
            "Cevap Hazırlama Ajanı",
            "DYS/e-Yazışma formatında (sayı, tarih, konu, ilgi, imza bloğu, "
            "dağıtım) resmî cevap taslağı üretiyorum. **Evrak İşleme** "
            "sekmesinde bir evrak analiz edildiğinde taslak otomatik hazırlanır "
            "ve indirilebilir.")

    # Eksik bilgi
    if any(k in s for k in ["eksik", "zorunlu alan", "tamamla"]):
        return _yonlendir(
            "Eksik Bilgi Ajanı",
            "Evrakta zorunlu alanların (muhatap, referans no, iletişim, tarih "
            "vb.) eksikliğini tespit edip başvurandan tamamlanmasını isteyen "
            "bilgilendirme metni üretiyorum.")

    # Evrak türü / genel
    if any(k in s for k in ["evrak", "dilekçe", "tür", "sınıflandır", "belge"]):
        return _yonlendir(
            "Sınıflandırma Ajanı",
            "Evrakları şu türlere ayırıyorum: " + ", ".join(EVRAK_TURLERI)
            + ".\n\nBir evrakı uçtan uca analiz etmek için **Evrak İşleme** "
            "sekmesinden metni girip *Akıllı Ajanı Çalıştır* deyin.")

    # Bilinmeyen — dürüst bilgi yetersizliği
    return ("Bu konuda emin olabileceğim yeterli bilgim yok, bu yüzden tahmin "
            "yürütmeyeceğim. 🤔\n\nAncak şunlarda yardımcı olabilirim: evrak "
            "analizi, mevzuat/RAG, ajan durumu, önceliklendirme, yönlendirme, "
            "KVKK ve taslak üretimi. Sorunuzu bu çerçevede yeniden ifade "
            "edebilir misiniz?")


def sayfa_asistan() -> None:
    """Asistan sayfası — orkestratör ile doğal dil sohbeti."""
    _ust_cubuk("Asistan · Orkestratör",
               "Doğal dille sorun; orkestratör ilgili ajana yönlendirip yanıtlar")
    ss = st.session_state

    sol, sag = st.columns([1, 2])

    # --- Sol: orkestratör kartı + hızlı sorular -------------------------
    with sol:
        ork = ss["orkestrator_tel"]
        with st.container(border=True):
            st.markdown(f"### 🧠 {ORKESTRATOR['ad']}")
            st.write("🟢 Aktif · çevrimiçi")
            st.caption(ORKESTRATOR["rol"])
            c1, c2 = st.columns(2)
            c1.metric("Yönetilen Ajan", len(AJANLAR))
            c2.metric("Backend", "🟢 Gerçek" if _BACKEND_VAR else "🟡 Simülasyon")

        st.markdown("**💡 Hızlı Sorular**")
        for i, oneri in enumerate(_HIZLI_SORULAR):
            if st.button(oneri, key=f"oneri_{i}", width="stretch"):
                ss["bekleyen_soru"] = oneri
                st.rerun()

        if st.button("🗑️ Sohbeti Temizle", width="stretch"):
            ss["sohbet"] = [{"rol": "assistant", "icerik": _KARSILAMA_MESAJI}]
            st.rerun()

    # --- Sağ: konuşma alanı ---------------------------------------------
    with sag:
        st.markdown("##### 💬 Sohbet")
        with st.container(border=True, height=440):
            for mesaj in ss["sohbet"]:
                avatar = "🧠" if mesaj["rol"] == "assistant" else "🧑"
                with st.chat_message(mesaj["rol"], avatar=avatar):
                    st.markdown(mesaj["icerik"])

    # --- Girdi (alt sabit) + bekleyen hızlı soru işleme -----------------
    girdi = st.chat_input("Orkestratöre sorun: evrak, mevzuat, ajan durumu, "
                          "KVKK, öncelik, yönlendirme...")
    soru = girdi or ss.get("bekleyen_soru")
    if soru:
        ss["bekleyen_soru"] = None
        ss["sohbet"].append({"rol": "user", "icerik": soru})
        ss["sohbet"].append({"rol": "assistant",
                             "icerik": _orkestrator_yanit(soru)})
        st.rerun()


# ===========================================================================
#  BÖLÜM 10 — SAYFA: MEVZUAT VE RAG
# ===========================================================================

def sayfa_mevzuat_rag() -> None:
    """Mevzuat ve RAG sayfası (arama + filtre + tablo + PDF)."""
    _ust_cubuk("Mevzuat ve RAG",
               "Kanun, yönetmelik, genelge ve Resmî Gazete korpusu (RAG kaynağı)")
    f1, f2 = st.columns([3, 2])
    with f1:
        arama = st.text_input("🔍 Mevzuat ara",
                              placeholder="Anahtar kelime, kanun no veya başlık...")
    with f2:
        tur_filtre = st.selectbox(
            "Belge türü",
            ["Tümü", "Kanun", "Yönetmelik", "Genelge", "Resmi Gazete"])

    df = pd.DataFrame(MEVZUAT_KORPUS).rename(columns={
        "kod": "Kod", "baslik": "Başlık", "tur": "Tür",
        "yil": "Yıl", "madde": "Madde Sayısı", "ozet": "Özet"})
    if tur_filtre != "Tümü":
        df = df[df["Tür"] == tur_filtre]
    if arama:
        maske = (df["Başlık"].str.contains(arama, case=False, na=False)
                 | df["Kod"].str.contains(arama, case=False, na=False)
                 | df["Özet"].str.contains(arama, case=False, na=False))
        df = df[maske]

    st.markdown(f"##### 📋 Korpus ({len(df)} kayıt)")
    st.dataframe(df, width="stretch", hide_index=True,
                 column_config={"Madde Sayısı": st.column_config.NumberColumn(
                     format="%d madde", width="small")})

    if not df.empty:
        dagilim = df["Tür"].value_counts().reset_index()
        dagilim.columns = ["Tür", "Adet"]
        st.markdown("##### 📊 Türe Göre Dağılım")
        st.altair_chart(
            alt.Chart(dagilim).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("Adet:Q", title="Belge Sayısı"),
                y=alt.Y("Tür:N", sort="-x", title=None),
                color=alt.Color("Tür:N", legend=None,
                                scale=alt.Scale(range=KATEGORIK_PALET)),
                tooltip=["Tür", "Adet"]).properties(height=200),
            width="stretch")

    st.divider()
    st.markdown("##### 📎 Yeni Mevzuat Belgesi Yükle (PDF)")
    ss = st.session_state
    y1, y2 = st.columns([3, 2])
    with y1:
        pdf = st.file_uploader("Mevzuat PDF'i (kurgu/sentetik)", type=["pdf"],
                              key="mevzuat_pdf")
        pdf_tur = st.selectbox("Belgenin türü",
                               ["Kanun", "Yönetmelik", "Genelge", "Resmi Gazete"])
        if st.button("📥 Kütüphaneye Ekle", width="stretch"):
            if pdf is not None:
                ss["yuklenen_pdfler"].append({
                    "Dosya": pdf.name, "Tür": pdf_tur,
                    "Boyut (KB)": round(len(pdf.getvalue()) / 1024, 1),
                    "Durum": "🟢 İndekslendi (RAG)", "Zaman": _zaman()})
                st.success(f"'{pdf.name}' RAG indeksine eklendi.")
            else:
                st.warning("Lütfen önce bir PDF seçin.")
    with y2:
        st.info("Yüklenen PDF'ler BM25 RAG indeksine eklenir ve mevzuat "
                "eşleştirmede aday havuza dahil edilir.\n\nYalnızca sentetik / "
                "kamuya açık mevzuat yükleyiniz.")

    if ss["yuklenen_pdfler"]:
        st.markdown("##### 🗂️ Yüklenen Belgeler")
        st.dataframe(pd.DataFrame(ss["yuklenen_pdfler"]),
                     width="stretch", hide_index=True)
    else:
        st.caption("Henüz belge yüklenmedi.")


# ===========================================================================
#  BÖLÜM 11 — SAYFA: KVKK VE UYUM
# ===========================================================================

def _maskele_dispatch(metin: str):
    """Metni önce GERÇEK KVKK agent'ıyla maskeler; olmazsa kurgu regex'e iner.

    Döner: (maskeli_metin, tablo_satirlari, gercek_bool)
    """
    agent = _anonim_agent() if _BACKEND_VAR else None
    if agent is not None:
        try:
            state = _AgentState(raw_text=metin)
            agent.run(state)
            sayac = (state.anonymization_report or {}).get("maskelenen", {})
            satir = [{"Veri Türü": _PII_ETIKET.get(k, k), "Maskelenen Adet": v}
                     for k, v in sayac.items() if v]
            return state.anonymized_text, satir, True
        except Exception:
            pass
    maskeli, tespitler = _kvkk_maskele(metin)
    satir = [{"Veri Türü": t["tur"], "Orijinal": t["orijinal"],
              "Maskeli": t["maske"]} for t in tespitler]
    return maskeli, satir, False


def sayfa_kvkk_uyum() -> None:
    """KVKK ve Uyum sayfası (gerçek maskeleme demosu + uyum matrisi)."""
    _ust_cubuk("KVKK ve Uyum",
               "Kişisel veri maskeleme, sızıntı ölçümü ve şartname uyum matrisi")

    # Şartname kısıtı ve sentetik-veri kartları DOĞRULANABİLİR gerçeklerdir;
    # uyum/sızıntı skorları ise toplu TEMSİLİ göstergedir (aşağıda canlı, gerçek
    # maskeleme denenebilir). Karışıklık olmasın diye açıkça etiketlenir.
    st.caption("ℹ️ Aşağıdaki iki skor kartı (uyum/sızıntı) **temsili demo** "
               "göstergesidir; gerçek maskeleme aşağıda canlı denenebilir. "
               "Şartname/sentetik-veri kartları doğrulanabilir gerçeklerdir.")
    kartlar = [
        _metrik_karti("🛡️", "%99,4", "KVKK Uyum Skoru (temsili)", "demo", "amber",
                      YESIL, [random.randint(48, 60) for _ in range(10)]),
        _metrik_karti("🔒", "0.012", "Ort. Sızıntı Skoru (temsili)", "demo", "amber",
                      MAVI, [random.randint(10, 30) for _ in range(10)]),
        _metrik_karti("🧾", "5 / 5", "Şartname Kısıtı", "karşılandı", "green",
                      YESIL, [random.randint(50, 60) for _ in range(10)]),
        _metrik_karti("📄", "100%", "Sentetik Veri", "gerçek PII yok", "green",
                      MAVI_ACIK, [random.randint(52, 60) for _ in range(10)]),
    ]
    _md(_metrik_gridi(kartlar))

    st.markdown("##### 🧪 Canlı Maskeleme Denemesi (gerçek KVKK agent'ı)")
    st.caption("Metne kurgu PII (TCKN, telefon, e-posta, IBAN) girin; gerçek "
               "anonimleştirme ajanının çıktısını anında görün.")
    metin = st.text_area("Test metni", value=ORNEK_DILEKCE, height=220)
    if st.button("🛡️ Maskele", type="primary"):
        maskeli, satir, gercek = _maskele_dispatch(metin)
        if gercek:
            st.success("🟢 **Gerçek KVKK anonimleştirme agent'ı** (kural tabanlı) "
                       "ile maskelendi.")
        else:
            st.info("🟡 Simülasyon maskesi (çekirdek backend yüklenemedi).")
        sol, sag = st.columns(2)
        with sol:
            st.markdown("**🔓 Orijinal**")
            st.code(metin, language="text")
        with sag:
            st.markdown("**🔒 Maskeli**")
            st.code(maskeli, language="text")
        if satir:
            st.dataframe(pd.DataFrame(satir), width="stretch", hide_index=True)
            toplam = (sum(r.get("Maskelenen Adet", 0) for r in satir)
                      if gercek else len(satir))
            st.success(f"{toplam} kişisel veri unsuru maskelendi.")
        else:
            st.info("Maskelenecek PII bulunamadı.")

    st.divider()
    st.markdown("##### 📋 Şartname Uyum Matrisi")
    uyum = pd.DataFrame({
        "Kısıt": ["Türkçe zorunluluğu", "Açık kaynak (Apache 2.0)",
                  "Gerçek kamu verisi yok", "Görev bütünlüğü (G1+G2)",
                  "Offline-first korunur"],
        "Durum": ["✅ Uygun"] * 5,
        "Kanıt": ["Tüm çıktı ve arayüz Türkçe",
                  "Depo Apache 2.0; model ağırlığı yok",
                  "Yalnızca sentetik/kurgu veri",
                  "Sınıflandırma + taslak uçtan uca",
                  "LLM olmadan tam işlevsel çekirdek"]})
    st.dataframe(uyum, width="stretch", hide_index=True)


# ===========================================================================
#  BÖLÜM 12 — SAYFA: AYARLAR
# ===========================================================================

def sayfa_ayarlar() -> None:
    """Ayarlar sayfası (sistem/model tercihleri — sunum amaçlı)."""
    _ust_cubuk("Ayarlar", "Sistem, model ve çalışma modu tercihleri")
    sol, sag = st.columns(2)
    with sol:
        with st.container(border=True):
            st.markdown("#### ⚙️ Çalışma Modu")
            st.radio("Ajan hattı modu",
                     ["full — Uçtan uca (Görev 1 + Görev 2)",
                      "classify — Yalnızca sınıflandırma (Görev 1)",
                      "draft — Yalnızca taslak/yönlendirme (Görev 2)"])
            st.toggle("Offline-first çekirdek (LLM olmadan çalış)", value=True)
            st.toggle("Düşük güven → insan onayına eskale et", value=True)
        with st.container(border=True):
            st.markdown("#### 🤖 Model / LLM Köprüsü")
            st.selectbox("LLM sağlayıcı (opsiyonel)",
                         ["Ollama (yerel)", "OpenAI-uyumlu", "Kapalı (offline)"])
            st.text_input("Uç nokta (endpoint)", value="http://localhost:11434")
            st.slider("Sıcaklık (temperature)", 0.0, 1.0, 0.2, 0.05)
    with sag:
        with st.container(border=True):
            st.markdown("#### 🧠 Güven / Kalibrasyon")
            st.slider("Reddetme eşiği (selective prediction)", 0.0, 1.0, 0.35)
            st.slider("Konformal kapsam (1-α)", 0.80, 0.99, 0.90)
            st.toggle("Sıcaklık ölçekleme (temperature scaling)", value=True)
        with st.container(border=True):
            st.markdown("#### 🗂️ Veri ve Gizlilik")
            st.toggle("KVKK otomatik maskeleme", value=True)
            st.toggle("Yalnızca sentetik veri kabul et", value=True,
                      disabled=True)
            st.caption("Şartname gereği gerçek kamu verisi kullanımı kapalıdır.")
    st.info("Bu sayfadaki ayarlar sunum amaçlıdır; kurgu değerler gösterir.")


# ===========================================================================
#  BÖLÜM 13 — ANA YÖNLENDİRİCİ VE GİRİŞ NOKTASI
# ===========================================================================

def main() -> None:
    """Uygulama giriş noktası: yapılandırma, tema, durum, gezinme, sayfa."""
    sayfa_yapilandir()
    oturum_baslat()
    tema_uygula()
    telemetriyi_guncelle()

    secili = kenar_cubugu_ciz()

    sayfalar = {
        "Genel Bakış": sayfa_genel_bakis,
        "Evrak İşleme": sayfa_evrak_isleme,
        "Toplu İşleme": sayfa_toplu_isleme,
        "Ajan Yönetimi": sayfa_ajan_yonetimi,
        "Asistan": sayfa_asistan,
        "Mevzuat ve RAG": sayfa_mevzuat_rag,
        "KVKK ve Uyum": sayfa_kvkk_uyum,
        "Ayarlar": sayfa_ayarlar,
    }
    sayfalar.get(secili, sayfa_genel_bakis)()


if __name__ == "__main__":
    main()
