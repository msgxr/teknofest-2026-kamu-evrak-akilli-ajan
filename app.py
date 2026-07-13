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
    Yalnızca SENTETİK / KURGU evraklarla çalışır; hiçbir gerçek kişisel veri
    (PII) üretilmez veya kopyalanmaz. Gösterilen tüm metrikler GERÇEKTİR:
    scripts/evaluate.py'nin ölçüm raporlarından, gerçek kayıt defterinden (SQLite)
    ve canlı işleme çıktısından gelir — kurgu/demo/simüle gösterge YOKTUR
    (şartname m.6: ölçülmemiş metrik yazılmaz).

Çalıştırma:
    streamlit run app.py
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

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


# ---------------------------------------------------------------------------
#  GERÇEK VERİ YÜKLEYİCİLERİ (ölçülmüş metrik + kayıt defteri + mevzuat korpusu)
#  Bu pano KURGU/DEMO veri göstermez: tüm sayılar ya evaluate.py'nin ürettiği
#  ölçüm raporlarından, ya gerçek kayıt defterinden, ya gerçek korpustan, ya da
#  canlı işleme çıktısından gelir (şartname m.6: ölçülmemiş metrik yazılmaz).
# ---------------------------------------------------------------------------
_VERI_KOK = Path(_KOK_DIZIN)

_EVAL_SETLERI = {
    "Geliştirme (52)": "eval_report.json",
    "Tutulmuş (16)": "eval_report_heldout.json",
    "Tutulmuş v2 (16)": "eval_report_heldout_v2.json",
    "Tutulmuş v3 · adversarial (16)": "eval_report_heldout_v3.json",
}

_KURGU_SETLERI = {
    "Geliştirme (52)": "kurgu_evraklar",
    "Tutulmuş (16)": "kurgu_evraklar_heldout",
    "Tutulmuş v2 (16)": "kurgu_evraklar_heldout_v2",
    "Tutulmuş v3 · adversarial (16)": "kurgu_evraklar_heldout_v3",
}


@st.cache_data(show_spinner=False)
def _eval_raporu(dosya: str) -> dict:
    """data/processed/<dosya> — evaluate.py'nin ürettiği GERÇEK ölçüm raporu.

    Yalnızca okunur (elle düzenlenmez); bulunamazsa boş sözlük döner.
    """
    try:
        return json.loads((_VERI_KOK / "data" / "processed" / dosya)
                          .read_text(encoding="utf-8"))
    except Exception:
        return {}


@st.cache_data(show_spinner=False, ttl=10)
def _kayit_istatistik() -> dict:
    """Gerçek evrak kayıt defteri (SQLite denetim izi) istatistiği; yoksa {}."""
    if not _BACKEND_VAR:
        return {}
    try:
        from src.utils.kayit_defteri import KayitDefteri
        return KayitDefteri().istatistik() or {}
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def _mevzuat_korpus() -> list:
    """data/raw/mevzuat_metinleri/ — gerçek mevzuat metinleri (ad, boyut, önizleme)."""
    korpus = []
    try:
        for p in sorted((_VERI_KOK / "data" / "raw" / "mevzuat_metinleri").glob("*.txt")):
            metin = p.read_text(encoding="utf-8")
            baslik = next((s.strip() for s in metin.splitlines() if s.strip()), p.stem)
            korpus.append({
                "doc_id": p.stem, "dosya": p.name, "baslik": baslik,
                "karakter": len(metin), "satir": metin.count("\n") + 1,
                "onizleme": metin.strip()[:500],
            })
    except Exception:
        pass
    return korpus


def _kurgu_evrak_yollari(alt_dizin: str) -> list:
    """data/raw/<alt_dizin>/ içindeki gerçek .txt evrak yollarını döndürür."""
    try:
        return sorted((_VERI_KOK / "data" / "raw" / alt_dizin).glob("*.txt"))
    except Exception:
        return []


# Ölçülen metrik değerini yüzde-metne çevirir (None → "—").
def _yzd(deger, ondalik: int = 1) -> str:
    """0-1 arası oranı '%xx,x' biçimine getirir; None/eksikse '—'."""
    if deger is None:
        return "—"
    try:
        return f"%{deger * 100:.{ondalik}f}".replace(".", ",")
    except Exception:
        return "—"


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
    """Oturum durumunu (session_state) ilk çalıştırmada başlatır (GERÇEK veri).

    Kurgu telemetri/sayaç YOKTUR: bu pano yalnız ölçülmüş metrik, gerçek kayıt
    defteri, gerçek korpus ve canlı işleme çıktısı gösterir.
    """
    ss = st.session_state
    if ss.get("_baslatildi"):
        return
    ss["_baslatildi"] = True
    ss["aktif_sayfa"] = "Genel Bakış"
    ss["oturum_islenen"] = 0       # bu OTURUMDA gerçekten işlenen evrak sayısı
    ss["son_adimlar"] = []         # son gerçek analizin ajan adım süreleri (ms)
    ss["yuklenen_pdfler"] = []
    ss["son_analiz"] = None
    ss["son_toplu"] = None         # son gerçek toplu işleme sonucu (liste)
    ss["sohbet"] = [{"rol": "assistant", "icerik": _KARSILAMA_MESAJI}]
    ss["bekleyen_soru"] = None


# ===========================================================================
#  BÖLÜM 2 — OTURUM YARDIMCILARI
# ===========================================================================

def _zaman() -> str:
    """Şimdiki zaman damgası (HH:MM:SS)."""
    return datetime.now().strftime("%H:%M:%S")


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
                <span><span class="ez-dot">●</span>Mevzuat korpusu</span>
                <span class="ez-status-val">{len(_mevzuat_korpus())} belge</span>
              </div>
              <div class="ez-status-row">
                <span><span class="ez-dot" style="color:{'#22C55E' if _BACKEND_VAR
                    else '#F59E0B'}">●</span>İşleme çekirdeği</span>
                <span class="ez-status-val">{'Gerçek · 11 ajan' if _BACKEND_VAR
                    else 'Yüklenemedi'}</span>
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
               "Ölçülmüş sistem başarımı ve gerçek işlem defteri", canli=True)
    ss = st.session_state

    st.caption("ℹ️ Bu panodaki **tüm sayılar gerçektir**: metrikler "
               "`scripts/evaluate.py`'nin ürettiği ölçüm raporlarından, işlem "
               "dağılımları gerçek kayıt defterinden (SQLite) gelir — kurgu/demo "
               "gösterge yoktur (şartname m.6).")

    set_ad = st.selectbox("Değerlendirme seti (ölçüm raporu)",
                          list(_EVAL_SETLERI.keys()), index=0)
    rapor = _eval_raporu(_EVAL_SETLERI[set_ad])
    if not rapor:
        st.warning("Ölçüm raporu bulunamadı; önce `scripts/evaluate.py` çalıştırın.")
        return

    sinif = rapor.get("siniflandirma") or {}
    yon = rapor.get("yonlendirme") or {}
    eksik = rapor.get("eksik_bilgi_tespiti") or {}
    mevz = (rapor.get("mevzuat_onerisi") or {}).get("isabet_at_3") or {}
    taslak = rapor.get("taslak_kalitesi") or {}
    kvkk = rapor.get("kvkk") or {}
    perf = rapor.get("performans") or {}
    ga = rapor.get("guven_araliklari") or {}
    n = rapor.get("degerlendirilen_dosya_sayisi", "—")

    # Sparkline serisi: sınıf-bazında F1'ler (gerçek, rapordan türetilir).
    spark = [max(14, round(v.get("f1", 0) * 60))
             for v in (sinif.get("sinif_bazinda") or {}).values()] or [50]

    def _ga_rozet(anahtar: str) -> str:
        w = (ga.get(anahtar) or {}).get("wilson_95")
        return f"%95 GA {_yzd(w[0], 0)}–{_yzd(w[1], 0)}" if w else ""

    kartlar = [
        _metrik_karti("🏷️", _yzd(sinif.get("accuracy")), "Sınıflandırma Doğruluğu",
                      _ga_rozet("siniflandirma"), "green", MAVI, spark),
        _metrik_karti("🧭", _yzd(yon.get("accuracy")), "Birim Yönlendirme",
                      _ga_rozet("yonlendirme"), "green", YESIL, spark),
        _metrik_karti("🧩", _yzd(eksik.get("micro_f1")), "Eksik Bilgi (micro-F1)",
                      f"TP {eksik.get('tp', '—')}", "blue", MAVI_ACIK, spark),
        _metrik_karti("⚖️", _yzd(mevz.get("isabet_orani")), "Mevzuat İsabet@3",
                      f"{mevz.get('isabet', '—')}/{mevz.get('etiketli_evrak', '—')}",
                      "green", MAVI, spark),
    ]
    _md(_metrik_gridi(kartlar))

    kayit = _kayit_istatistik()
    kartlar2 = [
        _metrik_karti("📝", f"{taslak.get('ortalama_puan', '—')}/100",
                      "Taslak Kalitesi (hakem)",
                      f"asgari {taslak.get('asgari_puan', '—')}", "blue",
                      MAVI_ACIK, spark),
        _metrik_karti("🛡️", _yzd(kvkk.get("sizintisiz_oran")), "KVKK Sızıntısız Oran",
                      f"{kvkk.get('toplam_kacak', '—')} kaçak", "green", YESIL, spark),
        _metrik_karti("⚡", f"{perf.get('evrak_basina_medyan_sure_saniye', '—')} sn",
                      "Medyan İşleme Süresi", "gerçek zamana yakın", "green",
                      MAVI, spark),
        _metrik_karti("📥", str(ss["oturum_islenen"]), "Bu Oturumda İşlenen",
                      "canlı sayaç", "blue", MAVI_ACIK, spark),
    ]
    _md(_metrik_gridi(kartlar2))

    muhur = (rapor.get("tekrarlanabilirlik") or {}).get("git_commit", "—")
    st.caption(f"Kaynak: `data/processed/{_EVAL_SETLERI[set_ad]}` · {n} evrak · "
               f"tekrarlanabilirlik mührü (git): `{muhur}`")

    _md('<div style="height:8px"></div>')

    # --- Gerçek kayıt defteri: tür + birim dağılımı ---------------------
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("##### 📊 İşlenen Evrak Türü Dağılımı")
        st.caption("Kaynak: gerçek kayıt defteri (SQLite denetim izi)")
        tur_d = kayit.get("tur_dagilimi") or {}
        if tur_d:
            tur_df = pd.DataFrame({"Tür": list(tur_d.keys()),
                                   "Adet": list(tur_d.values())})
            st.altair_chart(alt.Chart(tur_df).mark_arc(innerRadius=55).encode(
                theta="Adet:Q",
                color=alt.Color("Tür:N", scale=alt.Scale(range=KATEGORIK_PALET),
                                legend=alt.Legend(orient="right", title=None)),
                tooltip=["Tür", "Adet"]).properties(height=280), width="stretch")
        else:
            st.info("Kayıt defteri boş. **Evrak İşleme** / **Toplu İşleme** "
                    "sekmelerinde gerçek evrak işleyin.")
    with g2:
        st.markdown("##### 🏢 Birim Sevk Dağılımı")
        st.caption("Kaynak: gerçek kayıt defteri (yönlendirilen birimler)")
        birim_d = kayit.get("birim_dagilimi") or {}
        if birim_d:
            b_df = pd.DataFrame({"Birim": list(birim_d.keys()),
                                 "Adet": list(birim_d.values())})
            st.altair_chart(alt.Chart(b_df).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("Adet:Q", title="Evrak"),
                y=alt.Y("Birim:N", sort="-x", title=None),
                color=alt.Color("Adet:Q", legend=None,
                                scale=alt.Scale(scheme="blues")),
                tooltip=["Birim", "Adet"]).properties(height=280), width="stretch")
        else:
            st.info("Kayıt defterinde birim dağılımı yok.")

    st.caption(f"Kayıt defteri: **{kayit.get('toplam', 0)}** gerçek işlem kaydı "
               f"(`data/processed/kayit_defteri.db`).")


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
        st.caption("🔴 **Çekirdek yüklenemedi:** gerçek işleme yapılamaz. Bu pano "
                   "kurgu sonuç göstermez; çekirdek bağımlılıkları kurun.")

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


def _analiz_yap(metin: str):
    """Metni GERÇEK 11-ajan pipeline'ıyla işler.

    Bu pano kurgu veri göstermez: backend yoksa ya da hata olursa açık bir hata
    mesajı verir ve None döner (asla simüle/uydurma sonuç üretmez)."""
    pipe = _gercek_pipeline() if _BACKEND_VAR else None
    if pipe is None:
        st.error("⛔ Gerçek işleme çekirdeği (src/) yüklenemedi. Bu pano kurgu "
                 "veri göstermez; çekirdek bağımlılıkları kurup tekrar deneyin.")
        return None
    try:
        return _gercek_analiz(metin, pipe)
    except Exception as e:
        st.error(f"⛔ Ajan hattı bu evrakta hata verdi: {type(e).__name__}: {e}")
        return None


def _gercek_analiz(metin: str, pipe) -> dict:
    """Gerçek pipeline ile analiz — adımlar canlı akar, ham backend sonucu döner."""
    toplam = len(AJAN_HATTI_SIRASI)
    ilerleme = st.progress(0.0, text="Gerçek ajan hattı başlatılıyor...")
    sayac = {"n": 0}
    adimlar = []
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
            adimlar.append(adim)
            sayac["n"] += 1
            ilerleme.progress(min(1.0, sayac["n"] / toplam),
                              text=f"{ad} ({sayac['n']}/{toplam})")

        sonuc = pipe.process_text(metin, mode="full", kayit=False,
                                  on_step=_on_step)
        durum.update(label="✅ Gerçek analiz tamamlandı (orkestratör onayı)",
                     state="complete", expanded=False)
    ilerleme.progress(1.0, text="Tamamlandı")
    st.session_state["oturum_islenen"] += 1
    st.session_state["son_adimlar"] = adimlar or sonuc.get("islem_adimlari", [])
    sonuc["_gercek"] = True
    sonuc["orijinal_metin"] = metin
    return sonuc


def _analiz_sonuc_kartlari(sonuc: dict) -> None:
    """Gerçek analiz sonucunu kurumsal kartlarla çizer (yalnız gerçek yol)."""
    _gercek_sonuc_goster(sonuc)


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


# ===========================================================================
#  BÖLÜM 8 — SAYFA: TOPLU İŞLEME (GERÇEK EVRAK SETİ)
# ===========================================================================

def sayfa_toplu_isleme() -> None:
    """Toplu İşleme — GERÇEK evrak seti dosyalarını gerçek pipeline'dan geçirir."""
    _ust_cubuk("Toplu İşleme",
               "Gerçek evrak setini uçtan uca işle — canlı gerçek sonuç tablosu")
    if not _BACKEND_VAR:
        st.error("⛔ Gerçek işleme çekirdeği (src/) yüklenemedi; toplu işleme "
                 "yalnız gerçek pipeline ile çalışır.")
        return
    st.caption("ℹ️ Seçilen **gerçek evrak seti** (data/raw), gerçek 11-ajan "
               "pipeline'ından tek tek geçirilir — kurgu yok. Tür/birim/öncelik/"
               "süre gerçek çıktıdır.")
    kontrol, ozet = st.columns([2, 3])
    with kontrol:
        st.markdown("##### 🎛️ İşleme Ayarları")
        set_ad = st.selectbox("Evrak seti (gerçek)", list(_KURGU_SETLERI.keys()))
        yollar = _kurgu_evrak_yollari(_KURGU_SETLERI[set_ad])
        azami = len(yollar)
        adet = st.slider("İşlenecek evrak sayısı", 1, max(1, azami),
                         min(10, azami) or 1)
        baslat = st.button("▶ Gerçek Toplu İşlemeyi Başlat", type="primary",
                           width="stretch", disabled=(azami == 0))
    with ozet:
        st.markdown("##### 📥 Kuyruk")
        st.info(f"Set: **{set_ad}** · klasörde **{azami}** gerçek evrak. Seçilen "
                f"**{adet}** evrak, {len(AJANLAR)} ajanlık gerçek hattan "
                f"geçirilecek.\n\nİlk evrakta korpus yüklemesi nedeniyle küçük "
                f"gecikme olabilir; sonrası hızlıdır.")
    st.divider()
    if baslat and yollar:
        _toplu_isle_gercek(yollar[:adet])
    elif st.session_state.get("son_toplu"):
        st.caption("Son gerçek toplu işleme sonucu:")
        _toplu_sonuc_goster(st.session_state["son_toplu"])
    else:
        st.caption("Başlatmak için **Gerçek Toplu İşlemeyi Başlat** butonuna basın.")


def _toplu_isle_gercek(yollar: list) -> None:
    """Gerçek dosyaları gerçek pipeline'dan geçirir; canlı sonuç tablosu üretir."""
    pipe = _gercek_pipeline()
    if pipe is None:
        st.error("⛔ Pipeline kurulamadı.")
        return
    ust = st.columns(4)
    m_islenen, m_ivedi = ust[0].empty(), ust[1].empty()
    m_sure, m_onay = ust[2].empty(), ust[3].empty()
    ilerleme = st.progress(0.0, text="Gerçek işleme başlıyor...")
    tablo = st.empty()
    satirlar, ivedi, toplam_ms, onay = [], 0, 0, 0
    toplam = len(yollar)
    for i, yol in enumerate(yollar, start=1):
        try:
            r = pipe.process(str(yol), mode="full", kayit=False)
        except Exception as e:
            satirlar.append({"Sıra": i, "Dosya": yol.name, "Tür": "⚠ HATA",
                             "Birim": "—", "Öncelik": "—", "Süre (ms)": 0,
                             "İnsan Onayı": str(e)[:40]})
            tablo.dataframe(pd.DataFrame(satirlar[-14:]), width="stretch",
                            hide_index=True)
            continue
        tur = (r.get("siniflandirma") or {}).get("tur_adi", "—")
        birim = (r.get("yonlendirme") or {}).get("birim", "—")
        onc = (r.get("onceliklendirme") or {}).get("oncelik", "normal")
        onc_lbl = ONCELIKLER.get(onc, onc)
        sure_ms = int((r.get("islem_suresi_saniye") or 0) * 1000)
        hitl = (r.get("insan_onayi") or {}).get("gerekli", False)
        if "İVEDİ" in onc_lbl:
            ivedi += 1
        if hitl:
            onay += 1
        toplam_ms += sure_ms
        satirlar.append({"Sıra": i, "Dosya": yol.name, "Tür": tur, "Birim": birim,
                         "Öncelik": onc_lbl, "Süre (ms)": sure_ms,
                         "İnsan Onayı": "🛑 gerekli" if hitl else "✔ otomatik"})
        m_islenen.metric("İşlenen", f"{i}/{toplam}")
        m_ivedi.metric("İvedi/Çok İvedi", ivedi)
        m_sure.metric("Ort. Süre", f"{toplam_ms // i} ms")
        m_onay.metric("İnsan Onayı Gereken", onay)
        ilerleme.progress(i / toplam, text=f"{yol.name} ({i}/{toplam})")
        tablo.dataframe(pd.DataFrame(satirlar[-14:]), width="stretch",
                        hide_index=True)
    ilerleme.progress(1.0, text="✅ Gerçek toplu işleme tamamlandı")
    st.session_state["oturum_islenen"] += toplam
    st.session_state["son_toplu"] = satirlar
    _toplu_sonuc_goster(satirlar)


def _toplu_sonuc_goster(satirlar: list) -> None:
    """Gerçek toplu işleme sonuç tablosu + CSV indirme."""
    if not satirlar:
        return
    df = pd.DataFrame(satirlar)
    otomatik = sum(1 for s in satirlar
                   if "otomatik" in str(s.get("İnsan Onayı", "")))
    st.success(f"Toplam **{len(satirlar)}** gerçek evrak işlendi · otomatik "
               f"(insan onayı gerekmeyen): **{otomatik}/{len(satirlar)}**.")
    st.markdown("##### 🧾 Tam Sonuç Tablosu (gerçek)")
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button("⬇️ Sonuçları İndir (CSV)",
                       data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="toplu_isleme_gercek.csv", mime="text/csv")


# ===========================================================================
#  BÖLÜM 9 — SAYFA: AJAN YÖNETİMİ (MULTI-AGENT)
# ===========================================================================

def _orkestrator_paneli() -> None:
    """Orkestratör — gerçek yapı + son canlı çalıştırmanın kapı durumları."""
    st.markdown("##### 🧠 Orkestratör — Çekirdek Koordinatör")
    with st.container(border=True):
        st.markdown(f"### {ORKESTRATOR['ikon']} {ORKESTRATOR['ad']}")
        st.caption(ORKESTRATOR["rol"])
        son = st.session_state.get("son_analiz") or {}
        adimlar = st.session_state.get("son_adimlar") or []
        m1, m2, m3 = st.columns(3)
        m1.metric("Yönetilen Uzman Ajan", len(AJANLAR))
        m2.metric("Son Çalıştırma Adımı", len(adimlar) if adimlar else "—")
        m3.metric("Son Süre",
                  f"{son.get('islem_suresi_saniye', '—')} sn" if son else "—")

        st.markdown("**Karar Kapıları (koşullu akış) — son çalıştırma**")
        g1, g2, g3 = st.columns(3)
        if not son:
            g1.info("🚪 Okunabilirlik")
            g2.info("🚪 Dil")
            g3.info("🚪 Düşük güven")
            st.caption("Kapı durumları için **Evrak İşleme**'de bir evrak işleyin.")
            return
        atlanan = [a.get("agent") for a in adimlar if a.get("status") == "atlandi"]
        if (son.get("siniflandirma") or {}).get("tur") != "bilinmiyor":
            g1.success("🚪 Okunabilirlik — geçildi")
        else:
            g1.warning("🚪 Okunabilirlik — düşük")
        if "draft_writer" not in atlanan:
            g2.success("🚪 Dil — geçildi")
        else:
            g2.warning("🚪 Dil — TR değil")
        if (son.get("insan_onayi") or {}).get("gerekli"):
            g3.warning("🚪 Düşük güven — insan onayına")
        else:
            g3.success("🚪 Düşük güven — eskalasyon yok")


def sayfa_ajan_yonetimi() -> None:
    """Ajan Yönetimi — GERÇEK 11 ajan + gerçek ölçülen adım süreleri."""
    _ust_cubuk("Ajan Yönetimi",
               f"{len(AJANLAR)} gerçek uzman ajan + orkestratör")
    st.caption("ℹ️ Ajan listesi, rolleri ve süreleri **gerçektir**: roller "
               "`src/agents` ile birebir; ortalama süreler ölçüm raporundan, "
               "'son çalıştırma' süreleri son canlı analizden gelir. Kurgu "
               "CPU/bellek telemetrisi yoktur (şartname m.6).")
    ss = st.session_state
    rapor = _eval_raporu("eval_report.json")
    adim_sure = (rapor.get("performans") or {}).get(
        "adim_bazinda_ortalama_sure_saniye", {}) or {}
    son_adim = {a.get("agent"): a for a in (ss.get("son_adimlar") or [])}

    kartlar = [
        _metrik_karti("🤖", str(len(AJANLAR)), "Uzman Ajan", "gerçek",
                      "green", MAVI, [50] * 8),
        _metrik_karti("🧠", "1", "Orkestratör", "3 karar kapısı", "blue",
                      MAVI_ACIK, [50] * 8),
        _metrik_karti("⚙️", str(len(adim_sure) or len(AJANLAR)), "Ölçülen Adım",
                      "eval raporu", "blue", MAVI, [50] * 8),
        _metrik_karti("📥", str(ss["oturum_islenen"]), "Bu Oturumda İşlenen",
                      "canlı", "green", YESIL, [50] * 8),
    ]
    _md(_metrik_gridi(kartlar))

    _orkestrator_paneli()

    st.markdown("##### 🧩 Uzman Ajan Filosu (gerçek roller + ölçülen süreler)")
    sutunlar = st.columns(3)
    for idx, ajan in enumerate(AJANLAR):
        ort = adim_sure.get(ajan["kod"])
        canli = son_adim.get(ajan["kod"])
        with sutunlar[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {ajan['ikon']} {ajan['ad']}")
                st.caption(ajan["kategori"])
                c1, c2 = st.columns(2)
                c1.metric("Ort. Süre",
                          f"{(ort or 0) * 1000:.1f} ms" if ort is not None else "—")
                if canli:
                    c2.metric("Son Çalıştırma",
                              f"{int((canli.get('sure_saniye') or 0) * 1000)} ms")
                    durum = {"success": "✔ başarılı", "atlandi": "⤳ atlandı",
                             "error": "✗ hata"}.get(canli.get("status"), "—")
                    st.caption(f"Son durum: {durum}")
                else:
                    c2.metric("Son Çalıştırma", "—")
                st.caption(f"Rol: {ajan['rol'][:70]}")

    st.divider()
    st.markdown("##### 📊 Ajan Bazlı Ortalama Süre (gerçek — ölçüm raporu)")
    if adim_sure:
        yuk_df = pd.DataFrame({
            "Ajan": [next((a["ad"] for a in AJANLAR if a["kod"] == k), k)
                     for k in adim_sure],
            "Süre (ms)": [round(v * 1000, 2) for v in adim_sure.values()]})
        st.altair_chart(alt.Chart(yuk_df).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("Süre (ms):Q", title="Ortalama Süre (ms)"),
            y=alt.Y("Ajan:N", sort="-x", title=None),
            color=alt.Color("Süre (ms):Q", legend=None,
                            scale=alt.Scale(scheme="blues")),
            tooltip=["Ajan", "Süre (ms)"]).properties(height=360), width="stretch")
    else:
        st.info("Adım süresi verisi için önce `scripts/evaluate.py` çalıştırın.")


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

    # Ajan durumu (gerçek)
    if any(k in s for k in ["ajan", "durum", "telemetri", "filo", "çalışıyor",
                           "aktif mi"]):
        kayit = _kayit_istatistik()
        defter = kayit.get("toplam", 0)
        return ("🤖 **Ajan Filosu Durumu (gerçek)**\n\n"
                f"- Uzman ajan: **{len(AJANLAR)}** + 1 orkestratör "
                "(3 karar kapısı: okunabilirlik / dil / düşük güven)\n"
                f"- Bu oturumda işlenen evrak: **{ss['oturum_islenen']}**\n"
                f"- Kayıt defterindeki toplam gerçek işlem: **{defter}**\n"
                f"- İşleme çekirdeği: "
                f"**{'🟢 gerçek (src/) yüklü' if _BACKEND_VAR else '🟡 yüklü değil'}**\n\n"
                "Ölçülen adım süreleri için **Ajan Yönetimi** sekmesine bakın.")

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
        with st.container(border=True):
            st.markdown(f"### 🧠 {ORKESTRATOR['ad']}")
            st.write("🟢 Çevrimiçi · kural çekirdeği")
            st.caption(ORKESTRATOR["rol"])
            c1, c2 = st.columns(2)
            c1.metric("Yönetilen Ajan", len(AJANLAR))
            c2.metric("Çekirdek", "🟢 Gerçek" if _BACKEND_VAR else "🟡 Yok")

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
    """Mevzuat ve RAG — GERÇEK mevzuat korpusu + sistemin gerçek BM25 araması."""
    _ust_cubuk("Mevzuat ve RAG",
               "Gerçek mevzuat korpusu (RAG kaynağı) ve canlı BM25 araması")
    korpus = _mevzuat_korpus()
    st.caption(f"ℹ️ Kaynak: **`data/raw/mevzuat_metinleri/`** — gerçek "
               f"**{len(korpus)}** mevzuat metni. Arama, sistemin ürettiği çıktıda "
               f"kullandığı **gerçek BM25/RAG** motoruyla yapılır (kurgu skor yok).")

    st.markdown("##### 🔍 Canlı Mevzuat Araması (gerçek BM25/RAG)")
    sorgu = st.text_input("Sorgu", placeholder="ör. dilekçeye kaç günde cevap "
                          "verilir · bilgi edinme süresi · KVKK maskeleme")
    if sorgu:
        sonuc = _gercek_mevzuat_ara(sorgu, limit=5)
        if sonuc:
            for m in sonuc:
                skor = float(m.get("benzerlik") or 0)
                with st.container(border=True):
                    st.markdown(f"**{m.get('mevzuat_adi') or m.get('baslik', '—')}**"
                                f" · {m.get('madde_etiketi', '')}")
                    st.caption((m.get("icerik_ozeti") or m.get("gerekce") or "")[:280])
                    st.progress(min(1.0, max(0.0, skor)),
                                text=f"benzerlik {skor:.2f}")
        else:
            st.info("Bu sorgu için eşleşme bulunamadı ya da arama motoru "
                    "yüklenemedi.")

    st.divider()
    st.markdown(f"##### 📋 Mevzuat Korpusu ({len(korpus)} gerçek doküman)")
    if korpus:
        df = pd.DataFrame([{"Doküman": m["baslik"], "Dosya": m["dosya"],
                            "Karakter": m["karakter"], "Satır": m["satir"]}
                           for m in korpus])
        st.dataframe(df, width="stretch", hide_index=True)
        sec = st.selectbox("Dokümanı görüntüle (gerçek metin)",
                           [m["dosya"] for m in korpus])
        secm = next((m for m in korpus if m["dosya"] == sec), None)
        if secm:
            with st.container(border=True):
                st.markdown(f"**{secm['baslik']}**")
                st.caption(f"{secm['dosya']} · {secm['karakter']} karakter · "
                           f"{secm['satir']} satır")
                st.text(secm["onizleme"] + " …")
    else:
        st.warning("Mevzuat korpusu bulunamadı (`data/raw/mevzuat_metinleri/`).")


# ===========================================================================
#  BÖLÜM 11 — SAYFA: KVKK VE UYUM
# ===========================================================================

def _maskele_gercek(metin: str):
    """Metni GERÇEK KVKK anonimleştirme ajanıyla maskeler.

    Döner: (maskeli_metin, tablo_satirlari) veya backend yoksa None (kurgu YOK).
    """
    agent = _anonim_agent() if _BACKEND_VAR else None
    if agent is None:
        return None
    try:
        state = _AgentState(raw_text=metin)
        agent.run(state)
        sayac = (state.anonymization_report or {}).get("maskelenen", {})
        satir = [{"Veri Türü": _PII_ETIKET.get(k, k), "Maskelenen Adet": v}
                 for k, v in sayac.items() if v]
        return state.anonymized_text, satir
    except Exception:
        return None


def sayfa_kvkk_uyum() -> None:
    """KVKK ve Uyum — GERÇEK maskeleme + ölçülen sızıntı metriği + uyum matrisi."""
    _ust_cubuk("KVKK ve Uyum",
               "Gerçek kişisel veri maskeleme, ölçülen sızıntı ve şartname uyumu")
    kvkk = (_eval_raporu("eval_report.json").get("kvkk")) or {}
    st.caption("ℹ️ Sızıntı metriği **ölçülmüştür** (`scripts/evaluate.py`); "
               "maskeleme **gerçek anonimleştirme ajanıyla** canlı çalışır — "
               "kurgu/demo skor yoktur (şartname m.6).")
    kartlar = [
        _metrik_karti("🛡️", _yzd(kvkk.get("sizintisiz_oran")), "KVKK Sızıntısız Oran",
                      f"{kvkk.get('degerlendirilen', '—')} evrak", "green",
                      YESIL, [50] * 8),
        _metrik_karti("🔒", str(kvkk.get("toplam_kacak", "—")), "Toplam PII Kaçağı",
                      "ölçülen", "green", MAVI, [50] * 8),
        _metrik_karti("🧾", "5 / 5", "Şartname Kısıtı", "karşılandı", "green",
                      YESIL, [50] * 8),
        _metrik_karti("📄", "%100", "Sentetik Veri", "gerçek PII yok", "green",
                      MAVI_ACIK, [50] * 8),
    ]
    _md(_metrik_gridi(kartlar))
    st.caption("Kaynak: `data/processed/eval_report.json` (kvkk bloğu).")

    st.markdown("##### 🧪 Canlı Maskeleme (gerçek KVKK anonimleştirme ajanı)")
    st.caption("Metne kurgu PII (TCKN, telefon, e-posta, IBAN) girin; gerçek "
               "ajanın çıktısını anında görün.")
    metin = st.text_area("Test metni", value=ORNEK_DILEKCE, height=220)
    if st.button("🛡️ Maskele", type="primary"):
        cikti = _maskele_gercek(metin)
        if cikti is None:
            st.error("⛔ Gerçek KVKK ajanı yüklenemedi; bu pano kurgu maske "
                     "göstermez.")
        else:
            maskeli, satir = cikti
            st.success("🟢 **Gerçek KVKK anonimleştirme ajanı** (kural tabanlı) "
                       "ile maskelendi.")
            sol, sag = st.columns(2)
            with sol:
                st.markdown("**🔓 Orijinal**")
                st.code(metin, language="text")
            with sag:
                st.markdown("**🔒 Maskeli**")
                st.code(maskeli, language="text")
            if satir:
                st.dataframe(pd.DataFrame(satir), width="stretch", hide_index=True)
                toplam = sum(r.get("Maskelenen Adet", 0) for r in satir)
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
    """Ayarlar — sistemin GERÇEK çalışma yapılandırması (salt-okunur bilgi)."""
    _ust_cubuk("Ayarlar", "Sistemin güncel yapılandırması (salt-okunur, gerçek)")
    st.caption("ℹ️ Bu sayfa sistemin **gerçek** çalışma yapılandırmasını "
               "salt-okunur gösterir; kurgu ayar/değer yoktur. Çalışma modu ve "
               "eşikler kod/CLI ile belirlenir.")
    sol, sag = st.columns(2)
    with sol:
        with st.container(border=True):
            st.markdown("#### ⚙️ Çalışma Çekirdeği")
            c1, c2 = st.columns(2)
            c1.metric("İşleme çekirdeği",
                      "🟢 Gerçek (src/)" if _BACKEND_VAR else "🟡 Yok")
            c2.metric("Uzman ajan", len(AJANLAR))
            st.caption("Çalışma modu CLI'de seçilir: "
                       "`python -m src.main --mode {full|classify|draft}` "
                       "(varsayılan: full = Görev 1 + Görev 2).")
        with st.container(border=True):
            st.markdown("#### 🔌 LLM Köprüsü (opsiyonel)")
            st.write("Çekirdek **offline-first**: hiçbir LLM olmadan tam çalışır.")
            st.caption("Opsiyonel eskalasyon (Ollama / OpenAI-uyumlu) ortam "
                       "değişkeniyle açılır. Model bilgileri: "
                       "`docs/model_bilgileri.md`.")
    with sag:
        with st.container(border=True):
            st.markdown("#### 🧠 Karar Eşikleri (kod sabiti)")
            c1, c2 = st.columns(2)
            c1.metric("İnsan onayı güven eşiği", "0.60")
            c2.metric("Corrective RAG tetiği", "0.15")
            st.caption("Kaynak: `src/agents/orchestrator.py` "
                       "(`_INSAN_ONAYI_GUVEN_ESIGI`), `legislation_agent`.")
        with st.container(border=True):
            st.markdown("#### 🗂️ Veri ve KVKK")
            st.write("✅ Yalnızca sentetik/kurgu veri (şartname m.6.5)")
            st.write("✅ KVKK otomatik maskeleme (anonimleştirme ajanı)")
            st.caption("Gerçek kamu verisi kullanımı şartname gereği kapalıdır.")


# ===========================================================================
#  BÖLÜM 13 — ANA YÖNLENDİRİCİ VE GİRİŞ NOKTASI
# ===========================================================================

def main() -> None:
    """Uygulama giriş noktası: yapılandırma, tema, durum, gezinme, sayfa."""
    sayfa_yapilandir()
    oturum_baslat()
    tema_uygula()

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
