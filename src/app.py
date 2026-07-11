"""
Streamlit Demo Arayüzü — Kamu Evrak Akıllı Ajan Sistemi.

TEKNOFEST 2026 "Yapay Zeka Dil Ajanları Yarışması" (1. Senaryo) demo uygulaması.

Şartname Referansı:
    - Görev 1: Evrak Sınıflandırma ve İçerik Analizi
      (OCR/metin okuma, tür belirleme, bilgi çıkarımı, eksik bilgi tespiti,
       mevzuat önerisi, özet)
    - Görev 2: Resmî Yazı Taslaklama ve Birim Yönlendirme
      (taslak üretimi, format denetimi, birim yönlendirme, kullanıcı
       bilgilendirme, eksik bilgi talebi)
    - "Gerçek zamana yakın çalışma" → işlem adımları süreleriyle raporlanır.

Çalıştırma:
    streamlit run src/app.py

Tasarım notu:
    Modül import'u yan etkisizdir; tüm arayüz akışı main() içindedir.
    Streamlit betiği __main__ olarak çalıştırdığı için arayüz yalnızca
    `streamlit run` ile açılır, `import src.app` güvenlidir.
"""

from __future__ import annotations

import html
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# `streamlit run src/app.py` çağrısında sys.path'e yalnızca src/ eklenir;
# `from src....` import'larının çalışması için proje kökünü ekle.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from src.utils.eyazisma import uret_ustveri, ustveri_belge_tutarliligi
from src.utils.islem_raporu import uret_html_rapor
from src.utils.kokpit import kokpit_ozeti

logger = logging.getLogger("kamu_evrak_ajan.app")

# ---------------------------------------------------------------------------
# Sabitler (proje geneli sözlüklerle tutarlı)
# ---------------------------------------------------------------------------

DEMO_EVRAK_DIZINI = _PROJECT_ROOT / "data" / "raw" / "kurgu_evraklar"

# Kurum Kokpiti'nde toplu işlenebilecek kurgusal evrak kümelerinin kök dizini
VERI_KUMESI_KOKU = _PROJECT_ROOT / "data" / "raw"

# Geri bildirim döngüsü kayıt dosyası (JSONL; her satır bir düzeltme kaydı)
GERI_BILDIRIM_DOSYASI = _PROJECT_ROOT / "data" / "processed" / "geri_bildirim.jsonl"

ONCELIK_ROZETLERI = {
    "cok_ivedi": "🔴 ÇOK İVEDİ",
    "çok ivedi": "🔴 ÇOK İVEDİ",
    "ivedi": "🔴 İVEDİ",
    "gunlu": "🟠 GÜNLÜ",
    "günlü": "🟠 GÜNLÜ",
    "normal": "🟢 Normal",
}

EVRAK_TUR_ADLARI = {
    "dilekce": "Dilekçe",
    "ust_yazi": "Üst Yazı",
    "cevap_yazisi": "Cevap Yazısı",
    "bilgilendirme": "Bilgilendirme",
    "tutanak": "Tutanak",
    "rapor": "Rapor",
    "genelge": "Genelge",
    "onayli_belge": "Onaylı Belge",
    "diger": "Diğer",
}

ALAN_ETIKETLERI = {
    "tarihler": "Tarihler",
    "kurum_adlari": "Kurum Adları",
    "kisi_adlari": "Kişi Adları",
    "referans_numaralari": "Referans Numaraları",
    "konu": "Konu",
    "muhatap": "Muhatap",
    "sayilar": "Sayılar",
    "adresler": "Adresler",
    "iletisim": "İletişim Bilgileri",
}

MOD_ACIKLAMALARI = {
    "full": "full — Uçtan uca (Görev 1 + Görev 2)",
    "classify": "classify — Yalnızca sınıflandırma/analiz (Görev 1)",
    "draft": "draft — Yalnızca taslak/yönlendirme (Görev 2)",
}

YONTEM_ETIKETLERI = {
    "kural_tabanli": "🧩 Kural tabanlı",
    "kural": "🧩 Kural tabanlı",
    "rule_based": "🧩 Kural tabanlı",
    "llm": "🤖 LLM",
    "llm_eskalasyon": "🤖 LLM eskalasyon",
    "hibrit": "🧩🤖 Hibrit (kural + LLM)",
}

# Ajan hattı görselleştirmesi: orkestratördeki ajan kodları → okunur ad
AJAN_ADLARI = {
    "ocr": "OCR",
    "classification": "Sınıflandırma",
    "info_extraction": "Bilgi Çıkarım",
    "missing_info": "Eksik Bilgi",
    "legislation": "Mevzuat",
    "triage": "Önceliklendirme",
    "summarization": "Özet",
    "anonimlestirme": "KVKK Anonim.",
    "draft_writer": "Taslak Yazımı",
    "routing": "Yönlendirme",
    "user_info": "Bilgilendirme",
}

# islem_adimlari[].status → (ikon, kenarlık rengi, zemin rengi)
ADIM_DURUM_STILLERI = {
    "success": ("✅", "#2e7d32", "rgba(46, 125, 50, 0.10)"),
    "atlandi": ("⏭️", "#9e9e9e", "rgba(158, 158, 158, 0.12)"),
    "error": ("❌", "#c62828", "rgba(198, 40, 40, 0.10)"),
}


# ---------------------------------------------------------------------------
# Kaynak yükleme (bir kez kurulur)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Ajanlar yükleniyor...")
def _pipeline_kur():
    """
    Uçtan uca pipeline'ı bir kez kurar ve önbelleğe alır.

    Arayüz gerçek kullanım akışıdır: kayıt defteri (SQLite denetim izi)
    burada AÇIK kurulur; işlenen her evrak Kayıt Defteri sekmesinde
    listelenir. Değerlendirme betikleri ise varsayılan (kapalı) kurulumla
    çalışır ve etkilenmez.
    """
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    return EndToEndPipeline(kayit_defteri_aktif=True)


@st.cache_resource(show_spinner=False)
def _llm_bilgisi() -> dict:
    """LLM backend bilgisini bir kez tespit eder."""
    try:
        from src.models.llm_wrapper import get_default_llm

        llm = get_default_llm()
        return {
            "backend": llm.backend,
            "model": getattr(llm, "model_name", ""),
            "aktif": llm.is_available(),
        }
    except Exception as exc:  # LLM katmanı hiçbir koşulda arayüzü düşürmemeli
        logger.warning(f"LLM bilgisi alınamadı: {exc}")
        return {"backend": "offline", "model": "", "aktif": False}


# ---------------------------------------------------------------------------
# Yardımcı biçimlendirme fonksiyonları
# ---------------------------------------------------------------------------

def _fmt_yuzde(value: Any) -> str:
    """Güven/benzerlik skorunu %XX biçiminde döndürür (0-1 veya 0-100 girdili)."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v <= 1.0:
        v *= 100
    return f"%{v:.0f}"


def _oran_0_1(value: Any) -> float:
    """st.progress için değeri [0, 1] aralığına indirger."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v > 1.0:
        v /= 100.0
    return max(0.0, min(1.0, v))


def _fmt_deger(value: Any) -> str:
    """Çıkarılan bilgi değerini tablo hücresi için metne çevirir."""
    if value is None:
        return "—"
    if isinstance(value, str):
        return value.strip() or "—"
    if isinstance(value, (list, tuple, set)):
        parcalar = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parcalar) if parcalar else "—"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False) if value else "—"
    return str(value)


def _alan_adi(anahtar: str) -> str:
    """Alan anahtarını okunur Türkçe etikete çevirir."""
    return ALAN_ETIKETLERI.get(anahtar, anahtar.replace("_", " ").title())


def _yontem_rozeti(yontem: str) -> str:
    """Sınıflandırma yöntemini okunur rozet metnine çevirir."""
    if not yontem:
        return "—"
    return YONTEM_ETIKETLERI.get(str(yontem).strip().lower(), f"🔧 {yontem}")


def _oncelik_sirasi(oncelik: str) -> int:
    """Eksik bilgi öncelik sıralaması: kritik > önemli > diğer."""
    o = str(oncelik or "").strip().lower()
    if o == "kritik":
        return 0
    if o in ("onemli", "önemli"):
        return 1
    return 2


def _ajan_adi(kod: str) -> str:
    """Ajan kodunu okunur ada çevirir (bilinmeyen kod olduğu gibi döner)."""
    return AJAN_ADLARI.get(str(kod).strip().lower(), str(kod))


# ---------------------------------------------------------------------------
# Saf HTML üretim fonksiyonları (test edilebilir; Streamlit çağrısı içermez)
# ---------------------------------------------------------------------------

def _ajan_hatti_html(adimlar: list) -> str:
    """
    islem_adimlari verisinden soldan sağa bağlantılı ajan hattı HTML'i üretir.

    Her ajan için durum ikonu (✅/⏭️/❌), okunur ad ve süre gösterilir;
    en uzun süren başarılı adım rozetlenir. Çok-ajanlı mimariyi tek bakışta
    somutlaştıran demo bileşenidir.

    GÜVENLİK: tüm dinamik metinler html.escape ile kaçırılır (XSS önlemi);
    veri kendi pipeline'ımızdan gelse de ilke gereği kaçırma uygulanır.
    """
    gecerli = [a for a in (adimlar or []) if isinstance(a, dict)]
    if not gecerli:
        return ""

    # En uzun süren başarılı adımı bul (rozet için); tüm süreler 0 ise rozet yok
    en_uzun_indeks = -1
    en_uzun_sure = 0.0
    for i, adim in enumerate(gecerli):
        if adim.get("status") != "success":
            continue
        try:
            sure = float(adim.get("sure_saniye") or 0.0)
        except (TypeError, ValueError):
            continue
        if sure > en_uzun_sure:
            en_uzun_sure = sure
            en_uzun_indeks = i

    parcalar: list[str] = []
    for i, adim in enumerate(gecerli):
        durum = str(adim.get("status", "")).strip().lower()
        ikon, kenar, zemin = ADIM_DURUM_STILLERI.get(durum, ("🔹", "#607d8b", "rgba(96, 125, 139, 0.10)"))
        ad = html.escape(_ajan_adi(str(adim.get("agent", "—"))))

        # Süre etiketi: atlanmış adımda 'atlandı', hatada 'hata', diğerinde sn
        if durum == "atlandi":
            sure_metni = "atlandı"
        elif durum == "error":
            sure_metni = "hata"
        else:
            try:
                sure_metni = f"{float(adim.get('sure_saniye') or 0.0):.3f} sn"
            except (TypeError, ValueError):
                sure_metni = "—"

        # Fareyle üzerine gelince ayrıntı (açıklama + atlanma nedeni / hata)
        ipucu_parcalari = [str(adim.get("description", "")).strip()]
        if adim.get("neden"):
            ipucu_parcalari.append(f"Atlanma nedeni: {adim['neden']}")
        if adim.get("error"):
            ipucu_parcalari.append(f"Hata: {adim['error']}")
        ipucu = html.escape(" | ".join(p for p in ipucu_parcalari if p), quote=True)

        kesik = "dashed" if durum == "atlandi" else "solid"
        rozet = ""
        if i == en_uzun_indeks:
            rozet = (
                '<div style="margin-top:3px;"><span style="background:#1f3a5f;color:#ffffff;'
                'border-radius:999px;padding:1px 8px;font-size:0.62rem;white-space:nowrap;">'
                "⏱ en uzun adım</span></div>"
            )
        parcalar.append(
            f'<div title="{ipucu}" style="flex:0 0 auto;min-width:96px;text-align:center;'
            f"border:1.5px {kesik} {kenar};border-radius:10px;padding:6px 9px;"
            f'background:{zemin};">'
            f'<div style="font-size:1rem;line-height:1.2;">{ikon}</div>'
            f'<div style="font-size:0.76rem;font-weight:600;white-space:nowrap;">{ad}</div>'
            f'<div style="font-size:0.68rem;opacity:0.75;white-space:nowrap;">{html.escape(sure_metni)}</div>'
            f"{rozet}</div>"
        )

    ok = '<div style="flex:0 0 auto;font-weight:700;opacity:0.55;">→</div>'
    return (
        '<div style="display:flex;align-items:center;gap:6px;overflow-x:auto;'
        'padding:10px 4px;">' + ok.join(parcalar) + "</div>"
    )


def _a4_gorunum_html(taslak: str) -> str:
    """
    Yazı taslağını A4 kâğıt görünümünde HTML'e çevirir.

    Beyaz zemin, kenar boşlukları, hafif gölge; 'T.C.' ile başlayan antet
    bloğu (boş satıra veya 'Sayı' satırına kadar) ortalanır. Yazdırmaya
    uygundur (kâğıt oranı ~A4, 794px ≈ 21 cm @ 96dpi).

    GÜVENLİK: taslak metni html.escape ile kaçırılır (XSS önlemi) —
    taslak, kullanıcı girdisinden türetildiği için güvenilmez kabul edilir.
    """
    satirlar = (taslak or "").strip("\n").split("\n")
    baslik_satirlari: list[str] = []
    govde_baslangici = 0
    if satirlar and satirlar[0].strip().upper().startswith("T.C"):
        for satir in satirlar[:5]:  # antet en fazla 5 satır (T.C. + kurum + birim)
            temiz = satir.strip()
            if not temiz or temiz.lower().startswith(("sayı", "sayi")):
                break
            baslik_satirlari.append(temiz)
            govde_baslangici += 1
    govde = "\n".join(satirlar[govde_baslangici:]).strip("\n")

    baslik_html = ""
    if baslik_satirlari:
        baslik_ic = "<br>".join(html.escape(s) for s in baslik_satirlari)
        baslik_html = (
            '<div style="text-align:center;font-weight:700;letter-spacing:0.4px;'
            f'margin-bottom:20px;">{baslik_ic}</div>'
        )

    return (
        '<div style="background:#ffffff;color:#1a1a1a;max-width:794px;margin:0 auto;'
        "padding:56px 64px;border:1px solid #d0d4da;border-radius:3px;"
        "box-shadow:0 6px 24px rgba(15, 30, 60, 0.18);"
        "font-family:'Times New Roman', Georgia, serif;font-size:0.95rem;"
        'line-height:1.55;">'
        f"{baslik_html}"
        f'<div style="white-space:pre-wrap;">{html.escape(govde)}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Emsal evrak yardımcıları (kurumsal hafıza)
# ---------------------------------------------------------------------------

def _emsal_sorgu_metni(sonuc: dict) -> str:
    """
    Emsal araması için en uygun sorgu metnini seçer.

    Öncelik: ham evrak metni (arayüzde saklanır) > KVKK maskeli metin >
    özet + konu birleşimi. Böylece dosya türünden bağımsız olarak her
    sonuç için anlamlı bir sorgu üretilebilir.
    """
    ham = str(sonuc.get("_ham_metin") or "").strip()
    if ham:
        return ham
    anonim = sonuc.get("anonimlestirme")
    if isinstance(anonim, dict):
        maskeli = str(anonim.get("metin") or "").strip()
        if maskeli:
            return maskeli
    parcalar = [str(sonuc.get("ozet") or "").strip()]
    bilgi = sonuc.get("bilgi_cikarim")
    if isinstance(bilgi, dict):
        parcalar.append(str(bilgi.get("konu") or "").strip())
    return " ".join(p for p in parcalar if p).strip()


def _kendi_kaydi_mi(sonuc: dict, emsal: dict) -> bool:
    """
    Emsal kaydı, az önce işlenen evrakın kendi kayıt defteri izi mi?

    Aynı dosya adı = aynı evrak → emsal (geçmiş benzer evrak) sayılmaz.
    'dogrudan_metin' kaynağında dosya adı ayırt edici olmadığından ek
    olarak özet öneki karşılaştırılır (sezgisel; farklı metinler farklı
    özet üretir).
    """
    emsal_kaynak = Path(str(emsal.get("kaynak") or "")).name
    guncel_kaynak = Path(str(sonuc.get("input_file") or "")).name
    if not emsal_kaynak or emsal_kaynak != guncel_kaynak:
        return False
    if emsal_kaynak != "dogrudan_metin":
        return True
    guncel_ozet = str(sonuc.get("ozet") or "").strip()[:80]
    emsal_ozet = str(emsal.get("ozet") or "").strip()[:80]
    return bool(guncel_ozet) and guncel_ozet == emsal_ozet


# ---------------------------------------------------------------------------
# İşleme yardımcıları
# ---------------------------------------------------------------------------

def _dosya_isle(pipeline: Any, dosya_yolu: str, mode: str) -> dict:
    """Dosyayı pipeline üzerinden işler ve toplam süreyi garanti eder."""
    baslangic = time.time()
    sonuc = pipeline.process(dosya_yolu, mode=mode)
    sonuc.setdefault("islem_suresi_saniye", round(time.time() - baslangic, 2))
    # Emsal araması için ham metni sakla (yalnızca arayüz içi kullanım;
    # metin tabanlı dosyalarda; PDF/görüntüde özet/maskeli metne düşülür)
    try:
        yol = Path(dosya_yolu)
        if yol.suffix.lower() == ".txt":
            sonuc["_ham_metin"] = yol.read_text(encoding="utf-8")[:20_000]
    except Exception as exc:
        logger.debug(f"Ham metin saklanamadı (emsal araması özete düşer): {exc}")
    return sonuc


def _metin_isle(pipeline: Any, metin: str, mode: str) -> dict:
    """Doğrudan metin girişini pipeline üzerinden işler (kayıt defteri dahil)."""
    baslangic = time.time()
    sonuc = pipeline.process_text(metin, mode=mode)
    sonuc.setdefault("islem_suresi_saniye", round(time.time() - baslangic, 2))
    sonuc["_ham_metin"] = metin[:20_000]  # emsal araması için (arayüz içi)
    return sonuc


def _status_ile_isle(etiket: str, islem: Any) -> dict:
    """
    İşlemi st.status bloğu içinde çalıştırıp ajan akışı hissi verir.

    İşlem bittiğinde her ajan adımı durum ikonu ve süresiyle blok içinde
    listelenir; blok '✅ tamamlandı' durumuna çekilir. İşlem <1 sn sürse
    de jüri, 11 ajanlık hattın adım adım çalıştığını görür.

    Args:
        etiket: Status başlığında gösterilecek işlem etiketi
        islem: Parametresiz çağrılabilir; sonuç sözlüğü döndürür
    """
    with st.status(f"🤖 {etiket} — 11 ajanlık işlem hattı çalışıyor...", expanded=True) as durum:
        try:
            sonuc = islem()
        except Exception:
            durum.update(label=f"❌ {etiket} — işlem başarısız", state="error")
            raise
        adimlar = [a for a in (sonuc.get("islem_adimlari") or []) if isinstance(a, dict)]
        for adim in adimlar:
            ikon = ADIM_DURUM_STILLERI.get(str(adim.get("status", "")).strip().lower(), ("🔹",))[0]
            try:
                sure_metni = f"{float(adim.get('sure_saniye') or 0.0):.3f} sn"
            except (TypeError, ValueError):
                sure_metni = "—"
            st.write(
                f"{ikon} **{_ajan_adi(str(adim.get('agent', '—')))}** — "
                f"{adim.get('description', '')} ({sure_metni})"
            )
        durum.update(
            label=f"✅ {etiket} — {len(adimlar)} ajan adımı tamamlandı",
            state="complete",
            expanded=False,
        )
    return sonuc


def _ocr_bagimlilik_mesaji(sonuc: dict) -> Optional[str]:
    """OCR adımı bağımlılık eksikliğinden düştüyse anlaşılır mesaj üretir."""
    ocr_hatalari = [
        h for h in sonuc.get("hatalar", [])
        if isinstance(h, str) and h.lower().startswith("ocr")
    ]
    if not ocr_hatalari:
        return None

    detay = " | ".join(ocr_hatalari)
    ipuclari = []
    if "pytesseract" in detay or "tesseract" in detay.lower():
        ipuclari.append("Görüntü OCR için: `pip install pytesseract` + Tesseract kurulumu")
    if "pdf2image" in detay:
        ipuclari.append("Taranmış PDF için: `pip install pdf2image` + poppler kurulumu")
    if "PIL" in detay or "Pillow" in detay:
        ipuclari.append("Görüntü okuma için: `pip install Pillow`")
    if "easyocr" in detay:
        ipuclari.append("Alternatif OCR için: `pip install easyocr`")

    mesaj = f"Evrak metni okunamadı. Ayrıntı: {detay}"
    if ipuclari:
        mesaj += "\n\nÇözüm önerileri:\n- " + "\n- ".join(ipuclari)
    else:
        mesaj += "\n\nMetin tabanlı bir .txt dosyası veya doğrudan metin girişi deneyebilirsiniz."
    return mesaj


def _demo_etiketleri(demo_dizin: Path) -> dict:
    """
    Demo evrak klasöründeki etiketler.json dosyasını okur (varsa).

    Desteklenen biçimler:
        {"dosya.txt": "dilekce"}  veya
        {"dosya.txt": {"tur": "dilekce"}}  veya
        [{"dosya": "dosya.txt", "tur": "dilekce"}]
    """
    etiket_dosyasi = demo_dizin / "etiketler.json"
    if not etiket_dosyasi.exists():
        return {}
    try:
        veri = json.loads(etiket_dosyasi.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"etiketler.json okunamadı: {exc}")
        return {}

    etiketler: dict = {}
    if isinstance(veri, dict):
        for ad, deger in veri.items():
            if isinstance(deger, dict):
                tur = deger.get("tur") or deger.get("etiket") or deger.get("tur_adi") or ""
            else:
                tur = deger
            etiketler[str(ad)] = str(tur or "")
    elif isinstance(veri, list):
        for kayit in veri:
            if not isinstance(kayit, dict):
                continue
            ad = kayit.get("dosya") or kayit.get("file") or kayit.get("ad")
            tur = kayit.get("tur") or kayit.get("etiket") or kayit.get("tur_adi") or ""
            if ad:
                etiketler[str(ad)] = str(tur)
    return etiketler


# ---------------------------------------------------------------------------
# Sonuç görselleştirme bölümleri
# ---------------------------------------------------------------------------

def _metrik_satiri(sonuc: dict) -> None:
    """Üst satır özet metrik kartlarını çizer."""
    sinif = sonuc.get("siniflandirma") or {}
    yonlendirme = sonuc.get("yonlendirme") or {}
    format_denetimi = sonuc.get("format_denetimi") or {}

    tur = sinif.get("tur_adi") or EVRAK_TUR_ADLARI.get(sinif.get("tur", ""), "") or "Belirlenemedi"
    tur_guven = _fmt_yuzde(sinif.get("guven"))
    birim = yonlendirme.get("birim") or "Belirlenemedi"
    birim_guven = _fmt_yuzde(yonlendirme.get("guven"))
    sure = sonuc.get("islem_suresi_saniye")
    if isinstance(sure, (int, float)):
        sure_metni = f"{sure:.2f} sn" if sure >= 0.01 else "<0.01 sn"
    else:
        sure_metni = "—"
    skor = format_denetimi.get("skor")
    skor_metni = _fmt_yuzde(skor) if skor is not None else "—"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Evrak Türü", tur,
        f"güven {tur_guven}" if tur_guven != "—" else None,
        delta_color="off",
        help="Sınıflandırma ajanının tahmini (kural + istatistiksel model ensemble; "
             "gerekirse LLM eskalasyonu).",
    )
    k2.metric(
        "Önerilen Birim", birim,
        f"güven {birim_guven}" if birim_guven != "—" else None,
        delta_color="off",
        help="Yönlendirme ajanının önerdiği sorumlu birim ve karar güveni.",
    )
    k3.metric(
        "Toplam Süre", sure_metni,
        help="Uçtan uca işlem süresi — tüm ajan adımları dahil, gerçek ölçüm.",
    )
    k4.metric(
        "Format Skoru", skor_metni,
        help="Üretilen taslağın resmî yazışma kurallarına (başlık, sayı, konu, "
             "imza bloğu...) uygunluk skoru.",
    )


def _bolum_ajan_hatti(sonuc: dict) -> None:
    """
    Çok-ajanlı işlem hattını soldan sağa bağlantılı olarak görselleştirir.

    Her ajan için durum ikonu (✅ başarılı / ⏭️ atlandı / ❌ hata), ad ve
    süre gösterilir; en uzun süren adım rozetlenir. Koşullu kapıların
    atlattığı adımlar da görünür — mimari jüri gözünde somutlaşır.
    """
    adimlar = sonuc.get("islem_adimlari") or []
    st.subheader("🛰️ Çok-Ajanlı İşlem Hattı")
    hatti_html = _ajan_hatti_html(adimlar)
    if not hatti_html:
        st.info("İşlem adımı kaydı bulunmuyor.")
        return
    st.markdown(hatti_html, unsafe_allow_html=True)

    gecerli = [a for a in adimlar if isinstance(a, dict)]
    basarili = sum(1 for a in gecerli if a.get("status") == "success")
    atlanan = sum(1 for a in gecerli if a.get("status") == "atlandi")
    hatali = sum(1 for a in gecerli if a.get("status") == "error")
    ozet_parcalari = [f"✅ {basarili} başarılı"]
    if atlanan:
        ozet_parcalari.append(f"⏭️ {atlanan} atlandı (koşullu kapı)")
    if hatali:
        ozet_parcalari.append(f"❌ {hatali} hatalı (yedek yolla sürdürüldü)")
    st.caption(" • ".join(ozet_parcalari) + " — ayrıntılar sayfa sonundaki İşlem Adımları tablosunda.")


def _bolum_siniflandirma(sonuc: dict) -> None:
    """Görev 1: sınıflandırma sonucunu yöntem rozetiyle gösterir."""
    sinif = sonuc.get("siniflandirma") or {}
    st.subheader("🏷️ Sınıflandırma")
    if not sinif:
        st.info("Sınıflandırma sonucu üretilemedi.")
        return

    tur_adi = sinif.get("tur_adi") or EVRAK_TUR_ADLARI.get(sinif.get("tur", ""), sinif.get("tur", "—"))
    st.markdown(
        f"**Tür:** {tur_adi} (`{sinif.get('tur', '—')}`) &nbsp;•&nbsp; "
        f"**Güven:** {_fmt_yuzde(sinif.get('guven'))} &nbsp;•&nbsp; "
        f"**Yöntem:** {_yontem_rozeti(sinif.get('yontem', ''))}"
    )
    if sinif.get("aciklama"):
        st.caption(str(sinif["aciklama"]))


def _bolum_cikarilan_bilgiler(sonuc: dict) -> None:
    """Görev 1: çıkarılan önemli bilgi unsurlarını tablo olarak gösterir."""
    bilgiler = sonuc.get("bilgi_cikarim") or {}
    st.subheader("🔍 Çıkarılan Bilgiler")
    if not bilgiler:
        st.info("Çıkarılabilen bilgi unsuru bulunamadı.")
        return

    satirlar = [
        {"Alan": _alan_adi(anahtar), "Değer": _fmt_deger(deger)}
        for anahtar, deger in bilgiler.items()
    ]
    st.dataframe(satirlar, width="stretch", hide_index=True)


def _bolum_eksik_bilgiler(sonuc: dict) -> None:
    """Görev 1 + Görev 2: eksik bilgi tespiti ve eksik bilgi talepleri."""
    eksikler = sonuc.get("eksik_bilgiler") or []
    talepler = sonuc.get("eksik_bilgi_talepleri") or []

    st.subheader("⚠️ Eksik Bilgiler")
    if not eksikler:
        st.success("Evrakta kritik bir eksik bilgi tespit edilmedi.")
    else:
        for eksik in sorted(eksikler, key=lambda e: _oncelik_sirasi(e.get("oncelik", "")) if isinstance(e, dict) else 9):
            if not isinstance(eksik, dict):
                st.warning(str(eksik))
                continue
            oncelik = str(eksik.get("oncelik", "")).strip().lower()
            mesaj = f"**{_alan_adi(str(eksik.get('alan', 'alan')))}** — {eksik.get('aciklama', '')}"
            if eksik.get("oneri"):
                mesaj += f"\n\n💡 Öneri: {eksik['oneri']}"
            if oncelik == "kritik":
                st.error(f"🔴 [KRİTİK] {mesaj}")
            elif oncelik in ("onemli", "önemli"):
                st.warning(f"🟡 [ÖNEMLİ] {mesaj}")
            else:
                st.info(f"🔵 [{(oncelik or 'bilgi').upper()}] {mesaj}")

    if talepler:
        st.subheader("❓ Eksik Bilgi Talepleri")
        st.caption("Sistem, taslağın tamamlanabilmesi için aşağıdaki bilgileri talep etmektedir:")
        for i, talep in enumerate(talepler, 1):
            if not isinstance(talep, dict):
                st.markdown(f"{i}. {talep}")
                continue
            satir = f"**{i}. {talep.get('soru', talep.get('alan', ''))}**"
            detaylar = []
            if talep.get("gerekce"):
                detaylar.append(f"Gerekçe: {talep['gerekce']}")
            if talep.get("oncelik"):
                detaylar.append(f"Öncelik: {talep['oncelik']}")
            st.markdown(satir)
            if detaylar:
                st.caption(" • ".join(detaylar))


def _bolum_mevzuat(sonuc: dict) -> None:
    """Görev 1: ilgili mevzuat / yazışma kuralı önerileri."""
    eslesmeler = sonuc.get("mevzuat_eslestirme") or []
    st.subheader("📚 Mevzuat Önerileri")
    if not eslesmeler:
        st.info("Bu evrak için mevzuat önerisi üretilemedi.")
        return

    for i, kayit in enumerate(eslesmeler, 1):
        if not isinstance(kayit, dict):
            st.markdown(f"- {kayit}")
            continue
        baslik = kayit.get("baslik", f"Mevzuat {i}")
        benzerlik = kayit.get("benzerlik")
        madde = kayit.get("madde_etiketi") or ""
        ek_baslik = f" — {madde}" if madde else ""
        with st.expander(f"{i}. {baslik}{ek_baslik}  ({_fmt_yuzde(benzerlik)} benzerlik)"):
            if benzerlik is not None:
                st.progress(_oran_0_1(benzerlik))
            if kayit.get("icerik_ozeti"):
                st.markdown(str(kayit["icerik_ozeti"]))
            if kayit.get("gerekce"):
                st.caption(f"Gerekçe: {kayit['gerekce']}")
            if kayit.get("kaynak"):
                st.caption(f"Kaynak: {kayit['kaynak']}")


def _bolum_ozet(sonuc: dict) -> None:
    """Görev 1: evrak özeti."""
    st.subheader("📝 Özet")
    ozet = (sonuc.get("ozet") or "").strip()
    if ozet:
        with st.container(border=True):
            st.markdown(ozet)
    else:
        st.info("Özet üretilemedi.")


def _bolum_taslak(sonuc: dict, key_prefix: str) -> None:
    """Görev 2: resmî yazı taslağı + indirme düğmesi."""
    st.subheader("✍️ Yazı Taslağı")
    taslak = (sonuc.get("yazi_taslagi") or "").strip()
    if not taslak:
        st.info("Yazı taslağı üretilemedi (yalnızca 'classify' modunda bu bölüm boş kalır).")
        return

    yazi_turu = sonuc.get("yazi_turu") or "taslak"
    st.caption(f"Taslak türü: **{yazi_turu}**")
    duz_sekme, resmi_sekme = st.tabs(["📝 Düz Metin", "📜 Resmî Görünüm"])
    with duz_sekme:
        st.code(taslak, language=None)
    with resmi_sekme:
        # A4 kâğıt görünümü: metin html.escape ile kaçırılır (bkz. _a4_gorunum_html)
        st.markdown(_a4_gorunum_html(taslak), unsafe_allow_html=True)
        st.caption("🖨️ A4 kâğıt oranında resmî görünüm — yazdırmaya uygundur.")
    st.download_button(
        label="⬇️ Taslağı indir (.txt)",
        data=taslak.encode("utf-8"),
        file_name=f"yazi_taslagi_{yazi_turu}.txt",
        mime="text/plain",
        key=f"{key_prefix}_taslak_indir",
    )


def _bolum_format_denetimi(sonuc: dict) -> None:
    """Görev 2: resmî yazışma format denetimi kontrol listesi."""
    denetim = sonuc.get("format_denetimi") or {}
    st.subheader("✅ Format Denetimi")
    if not denetim:
        st.info("Format denetimi sonucu bulunmuyor.")
        return

    uygun = denetim.get("uygun")
    skor = denetim.get("skor")
    if uygun is True:
        st.success(f"Taslak resmî yazışma kurallarına uygun. Skor: {_fmt_yuzde(skor)}")
    elif uygun is False:
        st.warning(f"Taslakta format iyileştirmesi gereken noktalar var. Skor: {_fmt_yuzde(skor)}")
    elif skor is not None:
        st.markdown(f"**Skor:** {_fmt_yuzde(skor)}")

    kontroller = denetim.get("kontroller") or []
    for kontrol in kontroller:
        if isinstance(kontrol, dict):
            ad = (
                kontrol.get("kural")
                or kontrol.get("kontrol")
                or kontrol.get("ad")
                or kontrol.get("baslik")
                or kontrol.get("aciklama")
                or str(kontrol)
            )
            durum = kontrol.get("gecti", kontrol.get("uygun", kontrol.get("sonuc", kontrol.get("durum"))))
            if isinstance(durum, str):
                durum = durum.strip().lower() in ("true", "evet", "gecti", "geçti", "uygun", "ok", "basarili", "başarılı")
            isaret = "✅" if durum else "❌"
            detay = kontrol.get("detay") or kontrol.get("mesaj") or ""
            dayanak = kontrol.get("dayanak") or ""
            satir = f"{isaret} {ad}"
            if detay:
                satir += f" — _{detay}_"
            if dayanak:
                # Jüri önünde madde gösterilebilirlik: kuralın yönetmelik dayanağı
                satir += f" `{dayanak}`"
            st.markdown(satir)
        else:
            st.markdown(f"• {kontrol}")


def _bolum_yonlendirme(sonuc: dict) -> None:
    """Görev 2: birim yönlendirme önerisi, gerekçesi ve alternatifler."""
    yonlendirme = sonuc.get("yonlendirme") or {}
    st.subheader("🏢 Yönlendirme")
    if not yonlendirme:
        st.info("Yönlendirme önerisi üretilemedi.")
        return

    st.markdown(
        f"**Önerilen birim:** {yonlendirme.get('birim', '—')} "
        f"(`{yonlendirme.get('birim_kodu', '—')}`) &nbsp;•&nbsp; "
        f"**Güven:** {_fmt_yuzde(yonlendirme.get('guven'))}"
    )
    if yonlendirme.get("gerekce"):
        st.markdown(f"**Gerekçe:** {yonlendirme['gerekce']}")

    alternatifler = yonlendirme.get("alternatifler") or []
    if alternatifler:
        st.markdown("**Alternatif birimler:**")
        satirlar = []
        for alt in alternatifler:
            if isinstance(alt, dict):
                satirlar.append({
                    "Birim": alt.get("birim", "—"),
                    "Skor": alt.get("skor", alt.get("guven", "—")),
                })
            else:
                satirlar.append({"Birim": str(alt), "Skor": "—"})
        st.dataframe(satirlar, width="stretch", hide_index=True)


def _bolum_bilgilendirmeler(sonuc: dict) -> None:
    """Görev 2: kullanıcıya süreç bilgilendirmeleri."""
    bilgilendirmeler = sonuc.get("bilgilendirmeler") or []
    if not bilgilendirmeler:
        return

    st.subheader("📣 Süreç Bilgilendirmeleri")
    for kayit in bilgilendirmeler:
        if not isinstance(kayit, dict):
            st.info(str(kayit))
            continue
        seviye = str(kayit.get("seviye", "bilgi")).strip().lower()
        baslik = kayit.get("baslik", "Bilgilendirme")
        mesaj = kayit.get("mesaj", "")
        icerik = f"**{baslik}**\n\n{mesaj}"
        if seviye in ("hata", "error", "kritik"):
            st.error(icerik)
        elif seviye in ("uyari", "uyarı", "warning"):
            st.warning(icerik)
        elif seviye in ("basari", "başarı", "success"):
            st.success(icerik)
        else:
            st.info(icerik)


def _bolum_emsal(sonuc: dict) -> None:
    """
    Kurumsal Hafıza — Emsal Evraklar bölümü.

    Kayıt defterindeki geçmiş işlemler arasından, işlenen evraka metin
    benzerliğiyle en yakın emsalleri kart olarak gösterir. Emsal modülü
    (src/utils/emsal — paralel pakette geliştiriliyor) henüz yoksa bölüm
    sessizce gizlenir; arayüz kırılmaz.
    """
    try:
        from src.utils.emsal import emsal_ara
    except Exception:
        logger.debug("Emsal modülü bulunamadı; Kurumsal Hafıza bölümü gizlendi.")
        return

    sorgu = _emsal_sorgu_metni(sonuc)
    if not sorgu:
        return

    st.subheader("🧠 Kurumsal Hafıza — Emsal Evraklar")
    st.caption(
        "Kayıt defterinde daha önce işlenen evraklar arasından, bu evraka metin "
        "benzerliğiyle en yakın emsaller — geçmiş kararlarla tutarlılık sağlar."
    )
    # Kendi kaydını backend'de dışla (dosya adıyla); 'dogrudan_metin' kaynağında
    # ad ayırt edici olmadığından dışlama _kendi_kaydi_mi sezgiseline bırakılır.
    guncel_kaynak = Path(str(sonuc.get("input_file") or "")).name
    haric = guncel_kaynak if guncel_kaynak != "dogrudan_metin" else ""
    try:
        # Limit 5 istenir; kendi kaydı elendikten sonra en çok 3 gösterilir
        try:
            emsaller = emsal_ara(sorgu, limit=5, haric_kaynak=haric)
        except TypeError:
            # Geriye dönük uyumluluk: haric_kaynak parametresi olmayan sürüm
            emsaller = emsal_ara(sorgu, limit=5)
    except Exception as exc:
        logger.warning(f"Emsal araması başarısız: {exc}")
        st.caption("Emsal araması bu oturumda kullanılamıyor.")
        return

    secilenler = [
        e for e in (emsaller or [])
        if isinstance(e, dict) and not _kendi_kaydi_mi(sonuc, e)
    ][:3]

    if not secilenler:
        st.info(
            "📭 Kayıt defterinde henüz benzer evrak yok — sistem evrak işledikçe "
            "kurumsal hafıza oluşur ve emsaller burada listelenir."
        )
        return

    kolonlar = st.columns(len(secilenler))
    for kolon, emsal in zip(kolonlar, secilenler):
        with kolon, st.container(border=True):
            st.markdown(
                f"**{_fmt_yuzde(emsal.get('benzerlik'))} benzer** — "
                f"{emsal.get('tur_adi') or '—'}"
            )
            st.progress(_oran_0_1(emsal.get("benzerlik")))
            satirlar = [f"🏢 {emsal.get('birim') or '—'}"]
            if emsal.get("yazi_turu"):
                satirlar.append(f"✍️ Taslak türü: {emsal['yazi_turu']}")
            st.markdown("  \n".join(satirlar))
            ozet = str(emsal.get("ozet") or "").strip()
            if ozet:
                st.caption(ozet[:220] + ("…" if len(ozet) > 220 else ""))
            kunye = " • ".join(
                p for p in (
                    str(emsal.get("zaman") or "").strip(),
                    Path(str(emsal.get("kaynak") or "")).name,
                ) if p
            )
            if kunye:
                st.caption(f"🗂️ {kunye}")


def _bolum_islem_adimlari(sonuc: dict) -> None:
    """Meta: adım adım süre/durum tablosu (gerçek zamana yakın çalışma kanıtı)."""
    adimlar = sonuc.get("islem_adimlari") or []
    st.subheader("⏱️ İşlem Adımları")
    if not adimlar:
        st.info("İşlem adımı kaydı bulunmuyor.")
        return

    satirlar = []
    toplam = 0.0
    for adim in adimlar:
        if not isinstance(adim, dict):
            continue
        sure = adim.get("sure_saniye", 0.0)
        try:
            toplam += float(sure)
        except (TypeError, ValueError):
            pass
        durum = adim.get("status", "")
        if durum == "success":
            durum_metni = "✅ Başarılı"
        elif durum == "atlandi":
            durum_metni = f"⏭️ Atlandı ({adim.get('neden', 'koşullu kapı')})"
        else:
            durum_metni = f"❌ {adim.get('error', 'Hata')}"
        satirlar.append({
            "Ajan": adim.get("agent", "—"),
            "Adım": adim.get("description", "—"),
            "Durum": durum_metni,
            "Süre (sn)": f"{float(sure):.3f}" if isinstance(sure, (int, float)) else "—",
        })
    st.dataframe(satirlar, width="stretch", hide_index=True)
    st.caption(
        f"⚡ {len(satirlar)} ajan adımı toplam **{toplam:.2f} saniyede** tamamlandı — "
        "sistem gerçek zamana yakın çalışmaktadır."
    )

    hatalar = sonuc.get("hatalar") or []
    if hatalar:
        with st.expander(f"⚠️ İşlem uyarıları ({len(hatalar)})"):
            st.caption(
                "Aşağıdaki adımlarda sorun oluştu; sistem kural tabanlı "
                "yedek yollarla çalışmaya devam etti."
            )
            for hata in hatalar:
                st.markdown(f"- {hata}")


def _bolum_oncelik(sonuc: dict) -> None:
    """
    Önceliklendirme sonucu varsa öncelik rozetini ve son tarihi gösterir.

    Alan sonuçta yoksa bölüm sessizce gizlenir (guard'lı); entegrasyon
    ana oturumda yapılır.
    """
    oncelik_bilgisi = sonuc.get("onceliklendirme")
    if not isinstance(oncelik_bilgisi, dict) or not oncelik_bilgisi:
        return

    oncelik = str(oncelik_bilgisi.get("oncelik", "normal")).strip().lower()
    rozet = ONCELIK_ROZETLERI.get(oncelik, f"🏷️ {oncelik or 'normal'}")
    son_tarih = (
        oncelik_bilgisi.get("son_tarih")
        or oncelik_bilgisi.get("son_islem_tarihi")
        or oncelik_bilgisi.get("termin_tarihi")
    )

    k1, k2 = st.columns(2)
    k1.metric("Öncelik", rozet)
    k2.metric("Son Tarih", str(son_tarih) if son_tarih else "—")
    gerekce = oncelik_bilgisi.get("gerekce") or oncelik_bilgisi.get("aciklama")
    if gerekce:
        st.caption(f"Önceliklendirme gerekçesi: {gerekce}")


def _bolum_kvkk_nushasi(sonuc: dict, key_prefix: str) -> None:
    """
    Anonimleştirme sonucu varsa KVKK paylaşım nüshasını gösterir.

    Maskeli metin + maskeleme raporu + indirme düğmesi. Alan sonuçta
    yoksa bölüm sessizce gizlenir (guard'lı).
    """
    anonim = sonuc.get("anonimlestirme")
    if not isinstance(anonim, dict) or not anonim:
        return

    # Entegrasyon esnekliği: ana oturumun seçeceği anahtar adına toleranslı
    maskeli_metin = str(
        anonim.get("maskeli_metin")
        or anonim.get("anonim_metin")
        or anonim.get("anonymized_text")
        or anonim.get("metin")
        or ""
    ).strip()
    rapor = (
        anonim.get("maskeleme_raporu")
        or anonim.get("rapor")
        or anonim.get("anonymization_report")
        or anonim.get("maskelenen_alanlar")
        or anonim.get("maskelenen")
    )
    if not maskeli_metin and not rapor:
        return

    with st.expander("🔒 KVKK Paylaşım Nüshası"):
        st.caption(
            "Kişisel veriler maskelenmiş paylaşım nüshası — evrakın kurum "
            "dışıyla veya yetkisiz birimlerle paylaşımında bu nüsha kullanılır."
        )
        if maskeli_metin:
            st.code(maskeli_metin, language=None)
        if rapor:
            st.markdown("**Maskeleme raporu:**")
            if isinstance(rapor, list) and all(isinstance(r, dict) for r in rapor):
                st.dataframe(rapor, width="stretch", hide_index=True)
            else:
                st.json(rapor)
        if maskeli_metin:
            st.download_button(
                label="⬇️ Paylaşım nüshasını indir (.txt)",
                data=maskeli_metin.encode("utf-8"),
                file_name="kvkk_paylasim_nushasi.txt",
                mime="text/plain",
                key=f"{key_prefix}_kvkk_indir",
            )


def _bolum_eyazisma_ustveri(sonuc: dict, key_prefix: str) -> None:
    """
    e-Yazışma'dan esinlenen üstveri taslağını gösterir ve indirtir.

    Dürüstlük: resmî e-Yazışma şeması birebir uygulanmaz; EBYS
    entegrasyon vizyonunu gösteren bir TASLAKTIR (bkz. src/utils/eyazisma).
    """
    try:
        taslak_metni = str(sonuc.get("yazi_taslagi") or "")
        ustveri = uret_ustveri(sonuc, taslak_metni)
        tutarlilik = ustveri_belge_tutarliligi(ustveri, taslak_metni)
    except Exception as exc:  # üstveri hiçbir koşulda sonuç ekranını düşürmemeli
        logger.warning(f"e-Yazışma üstverisi üretilemedi: {exc}")
        return

    with st.expander("📦 e-Yazışma Üstverisi (taslak)"):
        st.caption(
            "e-Yazışma Paketi (CBDDO) yapısından **esinlenen** üstveri taslağı — "
            "EBYS entegrasyon vizyonunu gösterir; resmî şema birebir uygulanmamıştır."
        )
        # m.28/3: üstveri ile belge görüntüsü arasında fark olamaz —
        # ilke otomatik denetlenir ve sonucu burada gösterilir
        if tutarlilik.get("tutarli"):
            st.success(
                "Üstveri ↔ belge görüntüsü birebir tutarlı "
                f"(dayanak: {tutarlilik.get('dayanak', '')})"
            )
        else:
            farklar = [
                k["alan"] for k in tutarlilik.get("kontroller", [])
                if not k.get("tutarli")
            ]
            st.error(
                "Üstveri ile belge görüntüsü arasında fark var: "
                f"{', '.join(farklar)} (dayanak: {tutarlilik.get('dayanak', '')})"
            )
        st.json(ustveri)
        st.download_button(
            label="⬇️ Üstveriyi indir (.json)",
            data=json.dumps(ustveri, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="eyazisma_ustveri_taslak.json",
            mime="application/json",
            key=f"{key_prefix}_ustveri_indir",
        )


def _bolum_islem_raporu(sonuc: dict, key_prefix: str) -> None:
    """
    Tek tıkla indirilebilir HTML işlem denetim raporu düğmesi.

    Evrakın tüm işlem sonucunu kendine yeten, kurumsal görünümlü bir
    HTML raporuna döker (arşiv/denetim çıktısı; bkz. src/utils/islem_raporu).
    """
    try:
        rapor_html = uret_html_rapor(sonuc)
    except Exception as exc:  # rapor üretimi sonuç ekranını düşürmemeli
        logger.warning(f"HTML işlem raporu üretilemedi: {exc}")
        return

    dosya_koku = Path(str(sonuc.get("input_file", "evrak"))).stem or "evrak"
    st.download_button(
        label="📄 HTML İşlem Raporu İndir",
        data=rapor_html.encode("utf-8"),
        file_name=f"islem_raporu_{dosya_koku}.html",
        mime="text/html",
        key=f"{key_prefix}_islem_raporu_indir",
        help="Evrakın tüm işlem sonuçlarını içeren denetim raporu (arşive/denetime verilebilir).",
    )


def _birim_secenekleri() -> dict:
    """Yönlendirme birim seçeneklerini {kod: ad} olarak döndürür."""
    try:
        from src.agents.routing_agent import BIRIMLER

        return {kod: bilgi.get("ad", kod) for kod, bilgi in BIRIMLER.items()}
    except Exception as exc:
        logger.warning(f"Birim listesi yüklenemedi: {exc}")
        return {}


def _geri_bildirim_kaydet(kayit: dict) -> None:
    """Geri bildirim kaydını JSONL dosyasına ekler (dizini gerekirse açar)."""
    GERI_BILDIRIM_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    with GERI_BILDIRIM_DOSYASI.open("a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def _bolum_geri_bildirim(sonuc: dict, key_prefix: str) -> None:
    """
    Geri bildirim döngüsü: kullanıcı tür/birim tahminini düzeltebilir.

    Düzeltmeler data/processed/geri_bildirim.jsonl dosyasına eklenir ve
    kural kalibrasyonunda kullanılmak üzere biriktirilir.
    """
    sinif = sonuc.get("siniflandirma") or {}
    yonlendirme = sonuc.get("yonlendirme") or {}

    with st.expander("✍️ Sonucu Düzelt (geri bildirim)"):
        st.caption(
            "Tahmin hatalıysa doğru tür ve birimi seçip kaydedin; "
            "düzeltmeler kural kalibrasyonunda kullanılacaktır."
        )

        tur_kodlari = list(EVRAK_TUR_ADLARI.keys())
        tahmin_tur = str(sinif.get("tur", "")).strip()
        tur_index = tur_kodlari.index(tahmin_tur) if tahmin_tur in tur_kodlari else 0
        dogru_tur = st.selectbox(
            "Doğru evrak türü",
            tur_kodlari,
            index=tur_index,
            format_func=lambda k: EVRAK_TUR_ADLARI.get(k, k),
            key=f"{key_prefix}_gb_tur",
        )

        birimler = _birim_secenekleri()
        birim_kodlari = list(birimler.keys())
        dogru_birim = ""
        if birim_kodlari:
            tahmin_birim_kodu = str(yonlendirme.get("birim_kodu", "")).strip()
            birim_index = (
                birim_kodlari.index(tahmin_birim_kodu)
                if tahmin_birim_kodu in birim_kodlari
                else 0
            )
            dogru_birim = st.selectbox(
                "Doğru birim",
                birim_kodlari,
                index=birim_index,
                format_func=lambda k: birimler.get(k, k),
                key=f"{key_prefix}_gb_birim",
            )
        else:
            st.info("Birim listesi yüklenemediği için birim düzeltmesi kapalı.")

        if st.button("💾 Geri bildirimi kaydet", key=f"{key_prefix}_gb_kaydet"):
            kayit = {
                "zaman": datetime.now().isoformat(timespec="seconds"),
                "dosya": str(sonuc.get("input_file", "")),
                "tahmin_tur": tahmin_tur,
                "dogru_tur": dogru_tur,
                "tahmin_birim": str(yonlendirme.get("birim_kodu", "")).strip(),
                "dogru_birim": dogru_birim,
            }
            try:
                _geri_bildirim_kaydet(kayit)
                st.success(
                    "Geri bildirim kaydedildi — kural kalibrasyonunda kullanılacak."
                )
            except Exception as exc:
                logger.error(f"Geri bildirim kaydedilemedi: {exc}")
                st.error(f"Geri bildirim kaydedilemedi: {exc}")


def _sonuclari_goster(sonuc: dict, key_prefix: str) -> None:
    """Tüm sonuç bölümlerini düzenli bir yerleşimle çizer."""
    _metrik_satiri(sonuc)
    _bolum_oncelik(sonuc)  # önceliklendirme sonucu varsa gösterilir (guard'lı)
    _bolum_ajan_hatti(sonuc)  # çok-ajanlı hattın görsel akışı (demo kozu)
    _bolum_islem_raporu(sonuc, key_prefix)  # HTML denetim raporu indirme
    st.divider()

    sol, sag = st.columns(2, gap="large")
    with sol:
        _bolum_siniflandirma(sonuc)
        _bolum_cikarilan_bilgiler(sonuc)
        _bolum_eksik_bilgiler(sonuc)
        _bolum_mevzuat(sonuc)
        _bolum_ozet(sonuc)
    with sag:
        _bolum_taslak(sonuc, key_prefix)
        _bolum_format_denetimi(sonuc)
        _bolum_yonlendirme(sonuc)
        _bolum_bilgilendirmeler(sonuc)

    # Kurumsal hafıza: kayıt defterindeki benzer geçmiş evraklar (emsal)
    _bolum_emsal(sonuc)

    # Ek bölümler: KVKK nüshası (varsa), e-Yazışma üstverisi, geri bildirim
    _bolum_kvkk_nushasi(sonuc, key_prefix)
    _bolum_eyazisma_ustveri(sonuc, key_prefix)
    _bolum_geri_bildirim(sonuc, key_prefix)

    st.divider()
    _bolum_islem_adimlari(sonuc)


# ---------------------------------------------------------------------------
# Sekmeler
# ---------------------------------------------------------------------------

def _sekme_evrak_isle(pipeline: Any, mode: str) -> None:
    """Sekme 1: dosya yükleme veya doğrudan metin girişi ile evrak işleme."""
    st.caption(
        "Tek evrak uçtan uca işlenir: okuma → sınıflandırma → analiz → "
        "taslak → yönlendirme (11 ajanlık hat)."
    )
    st.markdown("Evrakı **dosya yükleyerek** veya **metni yapıştırarak** işleyebilirsiniz.")

    giris_turu = st.radio(
        "Giriş yöntemi",
        ["📎 Dosya yükle", "⌨️ Metin gir"],
        horizontal=True,
        label_visibility="collapsed",
    )

    yeni_sonuc: Optional[dict] = None

    if giris_turu == "📎 Dosya yükle":
        dosya = st.file_uploader(
            "Evrak dosyası seçin (TXT, PDF, PNG, JPG)",
            type=["txt", "pdf", "png", "jpg", "jpeg"],
            help="PDF metin katmanı pypdf ile okunur; taranmış PDF ve görüntüler için "
                 "OCR bağımlılıkları (pytesseract/pdf2image) gerekir.",
        )
        if dosya is not None and st.button("🚀 Dosyayı İşle", type="primary", key="dosya_isle_btn"):
            uzanti = Path(dosya.name).suffix.lower() or ".txt"
            gecici_yol = ""
            try:
                fd, gecici_yol = tempfile.mkstemp(suffix=uzanti, prefix="evrak_")
                with os.fdopen(fd, "wb") as f:
                    f.write(dosya.getbuffer())
                yeni_sonuc = _status_ile_isle(
                    f"'{dosya.name}' işleniyor",
                    lambda: _dosya_isle(pipeline, gecici_yol, mode),
                )
                yeni_sonuc["input_file"] = dosya.name  # geçici yol yerine özgün ad
            except Exception as exc:
                logger.error(f"Dosya işleme hatası: {exc}")
                st.error(
                    f"Dosya işlenirken bir sorun oluştu: {exc}\n\n"
                    "Dosyanın bozuk olmadığından ve formatın desteklendiğinden emin olun."
                )
            finally:
                if gecici_yol and os.path.exists(gecici_yol):
                    try:
                        os.unlink(gecici_yol)
                    except OSError:
                        # GÜVENLİK: evrak içeriği taşıyan geçici dosya
                        # silinemezse iz bırakmadan yutulmasın
                        logger.warning(f"Geçici evrak dosyası silinemedi: {gecici_yol}")
    else:
        metin = st.text_area(
            "Evrak metni",
            height=220,
            # GÜVENLİK: girdi karakter üst sınırı (kaynak tüketimi/DoS
            # koruması; orkestratördeki merkezî sınırla hizalı, tipik evrak
            # uzunluğunun çok üzerinde)
            max_chars=200_000,
            placeholder=(
                "Örn:\n\nSayın Yetkili,\n\n... Müdürlüğüne 15.03.2026 tarihinde verdiğim "
                "dilekçeme ilişkin bilgi almak istiyorum...\n\nAd Soyad / İmza"
            ),
        )
        if st.button("🚀 Metni İşle", type="primary", key="metin_isle_btn"):
            if not metin.strip():
                st.warning("Lütfen işlenecek bir evrak metni girin.")
            else:
                try:
                    yeni_sonuc = _status_ile_isle(
                        "Metin işleniyor",
                        lambda: _metin_isle(pipeline, metin, mode),
                    )
                except Exception as exc:
                    logger.error(f"Metin işleme hatası: {exc}")
                    st.error(f"Metin işlenirken bir sorun oluştu: {exc}")

    if yeni_sonuc is not None:
        st.session_state["sonuc_evrak"] = yeni_sonuc

    sonuc = st.session_state.get("sonuc_evrak")
    if sonuc:
        ocr_mesaji = _ocr_bagimlilik_mesaji(sonuc)
        if ocr_mesaji:
            st.error(ocr_mesaji)
            return
        st.success(f"İşlem tamamlandı: **{sonuc.get('input_file', 'evrak')}**")
        _sonuclari_goster(sonuc, key_prefix="evrak")


def _sekme_demo(pipeline: Any, mode: str) -> None:
    """Sekme 2: kurgusal demo evrakları üzerinde hızlı deneme."""
    st.caption("Hazır kurgusal örneklerle sistemi tek tıkla deneyin — jüri demosu için en hızlı yol.")
    st.markdown(
        "Aşağıdaki **kurgusal örnek evraklar** ile sistemi hızlıca deneyebilirsiniz. "
        "Örnekler gerçek kamu verisi içermez."
    )

    if not DEMO_EVRAK_DIZINI.exists():
        st.warning(f"Demo evrak dizini bulunamadı: `{DEMO_EVRAK_DIZINI}`")
        return

    dosyalar = sorted(DEMO_EVRAK_DIZINI.glob("*.txt"))
    if not dosyalar:
        st.warning("Demo dizininde .txt evrak bulunamadı.")
        return

    etiketler = _demo_etiketleri(DEMO_EVRAK_DIZINI)

    def _secenek_adi(yol: Path) -> str:
        etiket = etiketler.get(yol.name, "")
        if etiket:
            okunur = EVRAK_TUR_ADLARI.get(etiket, etiket)
            return f"{yol.name}  —  [{okunur}]"
        return yol.name

    secilen = st.selectbox(
        "Demo evrakı seçin",
        dosyalar,
        format_func=_secenek_adi,
    )

    if secilen is not None:
        try:
            icerik = secilen.read_text(encoding="utf-8")
        except Exception as exc:
            st.error(f"Evrak okunamadı: {exc}")
            return

        with st.expander("👁️ Evrak içeriğini önizle", expanded=True):
            st.code(icerik, language=None)

        if st.button("🚀 Bu evrakı işle", type="primary", key="demo_isle_btn"):
            try:
                sonuc = _status_ile_isle(
                    f"'{secilen.name}' işleniyor",
                    lambda: _dosya_isle(pipeline, str(secilen), mode),
                )
                st.session_state["sonuc_demo"] = sonuc
            except Exception as exc:
                logger.error(f"Demo evrak işleme hatası: {exc}")
                st.error(f"Demo evrak işlenirken bir sorun oluştu: {exc}")

    sonuc = st.session_state.get("sonuc_demo")
    if sonuc:
        st.divider()
        st.success(f"İşlem tamamlandı: **{Path(str(sonuc.get('input_file', ''))).name}**")
        _sonuclari_goster(sonuc, key_prefix="demo")


def _sekme_kokpit(pipeline: Any) -> None:
    """
    Sekme: Kurum Kokpiti — kurgusal evrak kümesini toplu işleyip kurum
    yönetimine yönelik özet göstergeleri (tür/birim dağılımı, eksiklik,
    süre, tahmini tasarruf) çizer.
    """
    st.caption("Kurum yönetimi görünümü: toplu işlem, dağılımlar ve tasarruf göstergeleri.")
    st.markdown(
        "Seçilen **kurgusal evrak kümesi** toplu işlenir ve kurum yönetimi için "
        "özet göstergeler üretilir. Örnekler gerçek kamu verisi içermez."
    )

    # Kurgusal evrak kümeleri (kurgu_evraklar, kurgu_evraklar_heldout, ...)
    kumeler = sorted(
        d.name for d in VERI_KUMESI_KOKU.glob("kurgu_evraklar*") if d.is_dir()
    )
    if not kumeler:
        st.warning(f"Kurgusal evrak kümesi bulunamadı: `{VERI_KUMESI_KOKU}`")
        return

    secilen_kume = st.selectbox("Evrak kümesi", kumeler, key="kokpit_kume")
    dosyalar = sorted((VERI_KUMESI_KOKU / secilen_kume).glob("*.txt"))
    st.caption(f"Kümede **{len(dosyalar)}** adet .txt evrak bulundu.")

    if dosyalar and st.button("🚀 Toplu İşle", type="primary", key="kokpit_isle_btn"):
        try:
            with st.spinner(f"'{secilen_kume}' kümesindeki {len(dosyalar)} evrak işleniyor..."):
                sonuclar = pipeline.process_batch([str(p) for p in dosyalar], mode="full")
            st.session_state["kokpit_sonuclar"] = sonuclar
            st.session_state["kokpit_kume_adi"] = secilen_kume
        except Exception as exc:
            logger.error(f"Toplu işlem hatası: {exc}")
            st.error(f"Toplu işlem sırasında bir sorun oluştu: {exc}")

    sonuclar = st.session_state.get("kokpit_sonuclar")
    if not sonuclar:
        return

    islenen_kume = st.session_state.get("kokpit_kume_adi", "")
    st.divider()
    st.success(f"Toplu işlem tamamlandı: **{islenen_kume}** ({len(sonuclar)} evrak)")

    ozet = kokpit_ozeti(sonuclar)

    # Üst satır metrik kartları
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Evrak Sayısı", str(ozet["evrak_sayisi"]),
        help="Bu toplu işlemde uçtan uca işlenen evrak sayısı.",
    )
    k2.metric(
        "Ort. İşlem Süresi", f"{ozet['ort_islem_suresi_sn']:.2f} sn",
        help="Evrak başına ortalama uçtan uca işlem süresi (gerçek ölçüm).",
    )
    k3.metric(
        "Eksikli Evrak Oranı", _fmt_yuzde(ozet["eksikli_evrak_orani"]),
        help="En az bir eksik bilgi unsuru tespit edilen evrakların oranı.",
    )
    k4.metric(
        "Kritik Eksikli Evrak", str(ozet["kritik_eksikli_sayisi"]),
        help="Kritik öncelikli eksik bilgi içeren evrak sayısı — öncelikli takip önerilir.",
    )
    if ozet.get("dusuk_guvenli_sayisi"):
        st.caption(
            f"⚠️ {ozet['dusuk_guvenli_sayisi']} evrak düşük güvenli karar içeriyor "
            "(insan onayı önerilir)."
        )

    # Dağılım grafikleri (pandas, streamlit'in zorunlu bağımlılığıdır)
    import pandas as pd

    g1, g2 = st.columns(2, gap="large")
    with g1:
        st.subheader("🏷️ Tür Dağılımı")
        if ozet["tur_dagilimi"]:
            st.bar_chart(pd.Series(ozet["tur_dagilimi"], name="Evrak sayısı"))
        else:
            st.info("Tür dağılımı üretilemedi.")
    with g2:
        st.subheader("🏢 Birim Dağılımı")
        if ozet["birim_dagilimi"]:
            st.bar_chart(pd.Series(ozet["birim_dagilimi"], name="Evrak sayısı"))
        else:
            st.info("Birim dağılımı üretilemedi.")

    # Tahmini tasarruf kutusu — varsayım şeffaf biçimde yazılır
    tasarruf = ozet["tahmini_tasarruf"]
    with st.container(border=True):
        st.subheader("⏳ Tahmini Zaman Tasarrufu")
        t1, t2, t3 = st.columns(3)
        t1.metric(
            "Manuel (tahmini)", f"{tasarruf['manuel_toplam_saat']:.1f} saat",
            help="Varsayıma dayalı tahmindir — evrak başına manuel işlem süresi "
                 "kabulünden hesaplanır (resmî kaynak yoktur).",
        )
        t2.metric(
            "Sistem (ölçülen)", f"{tasarruf['sistem_toplam_saniye']:.1f} sn",
            help="Sistemin bu kümeyi işlerken ölçülen gerçek toplam süresi.",
        )
        t3.metric(
            "Tasarruf Oranı", _fmt_yuzde(tasarruf["tasarruf_orani"]),
            help="Manuel varsayıma göre tasarruf — varsayım şeffaf biçimde alttaki notta yazılıdır.",
        )
        st.caption(
            f"ℹ️ Manuel süre, evrak başına **{tasarruf['manuel_dakika_varsayimi']} dakika** "
            "kabulüne dayanan bir **varsayımdır** (resmî bir kaynağa dayanmaz); "
            "sistem süresi ise gerçek ölçümdür."
        )

    # Sonuç tablosu
    st.subheader("📋 İşlem Sonuçları")
    satirlar = []
    for kayit in sonuclar:
        if not isinstance(kayit, dict):
            continue
        sinif = kayit.get("siniflandirma") or {}
        yonlendirme = kayit.get("yonlendirme") or {}
        satir = {
            "Dosya": Path(str(kayit.get("input_file", ""))).name or "—",
            "Tür": sinif.get("tur_adi") or sinif.get("tur") or "—",
            "Birim": yonlendirme.get("birim") or "—",
        }
        oncelik_bilgisi = kayit.get("onceliklendirme")
        if isinstance(oncelik_bilgisi, dict) and oncelik_bilgisi.get("oncelik"):
            satir["Öncelik"] = str(oncelik_bilgisi["oncelik"])
        sure = kayit.get("islem_suresi_saniye")
        satir["Süre (sn)"] = f"{float(sure):.2f}" if isinstance(sure, (int, float)) else "—"
        satirlar.append(satir)
    if satirlar:
        st.dataframe(satirlar, width="stretch", hide_index=True)

    # Evrak ilişki zinciri (yenilik): İlgi referansları ve konu/muhatap
    # benzerliğinden yazışma zincirleri (dilekçe → cevap → itiraz)
    if len(sonuclar) > 1:
        try:
            from src.utils.kokpit import kokpit_iliskiler

            iliskiler = kokpit_iliskiler(sonuclar)
            zincirler = iliskiler.get("zincirler") or []
            with st.container(border=True):
                st.subheader("🔗 Evrak İlişki Zinciri")
                if zincirler:
                    for zincir in zincirler:
                        evraklar = " → ".join(
                            Path(str(ad)).name for ad in zincir.get("evraklar", [])
                        )
                        st.markdown(
                            f"- **{evraklar}**  \n"
                            f"  _{zincir.get('aciklama', '')}_ "
                            f"(bağlantı: {zincir.get('baglanti_turu', '?')})"
                        )
                    st.caption(
                        f"ℹ️ {len(zincirler)} zincir, "
                        f"{len(iliskiler.get('bagimsiz') or [])} bağımsız evrak."
                    )
                else:
                    st.caption(
                        "Bu kümede İlgi referansı veya konu benzerliğiyle "
                        "bağlanan evrak zinciri bulunamadı."
                    )
        except Exception as exc:  # zincir analizi kokpiti düşürmesin
            st.caption(f"İlişki zinciri analizi yapılamadı: {exc}")


def _sekme_kayit_defteri(pipeline: Any) -> None:
    """
    Sekme: Kayıt Defteri — işlenen evrakların SQLite denetim izi.

    Kamu evrak yönetimindeki 'evrak kayıt defteri' pratiğinin karşılığı:
    arayüzde işlenen her evrak tek satırlık denetim kaydıyla listelenir,
    tür/birim/öncelik/serbest metin ölçütleriyle filtrelenebilir.
    """
    st.caption("Denetim izi görünümü: işlenen her evrakın kalıcı SQLite kaydı ve sorgulama.")
    st.markdown(
        "Bu arayüzde işlenen her evrak, **denetlenebilirlik** için evrak kayıt "
        "defterine (SQLite) işlenir — kamu evrak sistemlerindeki kayıt defteri / "
        "denetim izi (audit trail) pratiğinin karşılığıdır."
    )

    defter = getattr(pipeline, "kayit_defteri", None)
    if defter is None:
        st.info(
            "Kayıt defteri bu oturumda etkin değil (pipeline kayıt kapalı kuruldu "
            "veya veritabanı açılamadı)."
        )
        return

    try:
        istatistik = defter.istatistik()
    except Exception as exc:
        logger.error(f"Kayıt defteri istatistiği okunamadı: {exc}")
        st.error(f"Kayıt defteri okunamadı: {exc}")
        return

    if not istatistik.get("toplam"):
        st.info(
            "📭 Kayıt defteri henüz boş.\n\n"
            "**Evrak İşle**, **Demo Evrakları** veya **Kurum Kokpiti** sekmesinde "
            "bir evrak işlediğinizde, işlem burada denetim kaydı olarak listelenir."
        )
        return

    # İstatistik kartları
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Toplam Kayıt", str(istatistik["toplam"]),
        help="Kayıt defterindeki (SQLite denetim izi) toplam işlem kaydı.",
    )
    k2.metric(
        "Ort. İşlem Süresi", f"{istatistik['ort_sure_saniye']:.2f} sn",
        help="Kayıtlı işlemlerin ortalama uçtan uca süresi (gerçek ölçüm).",
    )
    k3.metric(
        "İnsan Onayı Gerekli", str(istatistik["insan_onayi_sayisi"]),
        help="Düşük güvenli karar nedeniyle insan onayına işaretlenen işlem sayısı "
             "(koşullu kapı 3).",
    )
    k4.metric(
        "Kritik Eksikli", str(istatistik["kritik_eksikli_sayisi"]),
        help="Kritik öncelikli eksik bilgi tespit edilen kayıt sayısı.",
    )

    # Dağılım grafikleri (pandas, streamlit'in zorunlu bağımlılığıdır)
    import pandas as pd

    g1, g2 = st.columns(2, gap="large")
    with g1:
        st.subheader("🏷️ Tür Dağılımı")
        tur_dagilimi = {
            EVRAK_TUR_ADLARI.get(kod, kod): adet
            for kod, adet in (istatistik.get("tur_dagilimi") or {}).items()
        }
        if tur_dagilimi:
            st.bar_chart(pd.Series(tur_dagilimi, name="Kayıt sayısı"))
        else:
            st.info("Tür dağılımı üretilemedi.")
    with g2:
        st.subheader("🏢 Birim Dağılımı")
        if istatistik.get("birim_dagilimi"):
            st.bar_chart(pd.Series(istatistik["birim_dagilimi"], name="Kayıt sayısı"))
        else:
            st.info("Birim dağılımı üretilemedi.")

    # Filtreler — seçenekler defterde GERÇEKTEN geçen değerlerden üretilir
    st.subheader("🔎 Kayıt Sorgulama")
    TUMU = "(Tümü)"
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        tur_secimi = st.selectbox(
            "Evrak türü",
            [TUMU] + sorted(istatistik.get("tur_dagilimi") or {}),
            format_func=lambda k: EVRAK_TUR_ADLARI.get(k, k),
            key="kd_tur",
        )
    with f2:
        birim_secimi = st.selectbox(
            "Birim",
            [TUMU] + sorted(istatistik.get("birim_dagilimi") or {}),
            key="kd_birim",
        )
    with f3:
        oncelik_secimi = st.selectbox(
            "Öncelik",
            [TUMU] + sorted(istatistik.get("oncelik_dagilimi") or {}),
            key="kd_oncelik",
        )
    with f4:
        metin_ara = st.text_input(
            "Metin ara (özet/kaynak)",
            key="kd_metin",
            placeholder="örn. su kesintisi",
        )

    try:
        kayitlar = defter.sorgula(
            tur=None if tur_secimi == TUMU else tur_secimi,
            birim=None if birim_secimi == TUMU else birim_secimi,
            oncelik=None if oncelik_secimi == TUMU else oncelik_secimi,
            metin_ara=metin_ara.strip() or None,
            limit=50,
        )
    except Exception as exc:
        logger.error(f"Kayıt defteri sorgusu başarısız: {exc}")
        st.error(f"Kayıtlar sorgulanamadı: {exc}")
        return

    if not kayitlar:
        st.warning("Bu ölçütlerle eşleşen kayıt bulunamadı.")
        return

    satirlar = []
    for kayit in kayitlar:
        satirlar.append({
            "No": kayit.get("id"),
            "Zaman": kayit.get("zaman"),
            "Kaynak": Path(str(kayit.get("kaynak") or "")).name or "—",
            "Tür": EVRAK_TUR_ADLARI.get(str(kayit.get("tur")), kayit.get("tur")) or "—",
            "Birim": kayit.get("birim") or "—",
            "Öncelik": kayit.get("oncelik") or "—",
            "Son Tarih": kayit.get("son_tarih") or "—",
            "Eksik": kayit.get("eksik_sayisi"),
            "Kritik": "⚠️" if kayit.get("kritik_eksik") else "—",
            "Format": _fmt_yuzde(kayit.get("format_skoru")),
            "Süre (sn)": kayit.get("sure_saniye"),
            "İnsan Onayı": "✋" if kayit.get("insan_onayi") else "—",
            "Özet (ilk 200)": kayit.get("ozet_ilk_200") or "—",
        })
    st.dataframe(satirlar, width="stretch", hide_index=True)
    st.caption(
        f"En yeni {len(satirlar)} kayıt gösteriliyor (azami 50). "
        "Kayıtlar `data/processed/kayit_defteri.db` dosyasında kalıcıdır."
    )


def _sekme_hakkinda() -> None:
    """Sekme 3: mimari özeti, görev eşleşmesi ve veri kullanımı notu."""
    st.caption("Sistemin mimarisi, şartname görev eşleşmesi ve veri kullanımı ilkeleri.")
    st.subheader("Mimari Özeti")
    st.markdown(
        "Sistem, bir **orkestratör** tarafından koordine edilen **11 uzman ajandan** oluşur. "
        "Her ajan paylaşılan durum nesnesini (`AgentState`) okuyup kendi alanlarını doldurur; "
        "LLM erişilemezse tüm ajanlar **kural tabanlı** yedek yollarla tam işlevli çalışır. "
        "Sınıflandırma, kural puanlayıcı ile eğitilmiş istatistiksel modelin **hibrit "
        "ensemble** birleşimidir; akıştaki **koşullu kapılar** okunamayan metni, Türkçe "
        "olmayan evrakı ve düşük güvenli kararları yakalayıp gerekirse **insan onayına** işaretler."
    )
    st.markdown(
        """
| # | Ajan | Görevi | Şartname Görevi |
|---|------|--------|-----------------|
| 1 | OCR Agent | PDF/görüntü/metinden metin çıkarımı | Görev 1 |
| 2 | Classification Agent | Evrak türü belirleme (kural ⊕ istatistiksel model ensemble, düşük güvende LLM eskalasyonu) | Görev 1 |
| 3 | Info Extraction Agent | Tarih, kurum, kişi, sayı, konu, muhatap çıkarımı | Görev 1 |
| 4 | Missing Info Agent | Eksik bilgi unsurlarının tespiti | Görev 1 |
| 5 | Legislation Agent | İlgili mevzuat / yazışma kuralı önerisi (BM25) | Görev 1 |
| 6 | Triage Agent | Aciliyet / yasal süre tespiti ve önceliklendirme | Görev 1 |
| 7 | Summarization Agent | Kısa evrak özeti | Görev 1 |
| 8 | Anonimleştirme Agent | KVKK paylaşım nüshası (kişisel veri maskeleme) | Görev 1 |
| 9 | Draft Writer Agent | Resmî yazı taslağı + format denetimi | Görev 2 |
| 10 | Routing Agent | Doğru birime yönlendirme önerisi | Görev 2 |
| 11 | User Info Agent | Süreç bilgilendirmesi + eksik bilgi talebi | Görev 2 |
| — | Orchestrator | Akış koordinasyonu, koşullu kapılar, süre/güven izleme | Görev 1 + 2 |
"""
    )

    st.subheader("Mimari Şema")
    st.code(
        """
Evrak (TXT / PDF / Görüntü / doğrudan metin)
        │
        ▼
  [1] OCR ──► ◇ KAPI 1: metin okunabilir mi? ── hayır ──► adımlar atlanır + insan onayı
        │ evet
        ▼
┌── GÖREV 1 · Sınıflandırma ve İçerik Analizi ────────────────────────────────┐
│ [2] Sınıflandırma (kural ⊕ istatistiksel model = hibrit ensemble)           │
│      └─ ◇ KAPI 3a: güven düşükse LLM eskalasyonu / insan onayı              │
│ [3] Bilgi Çıkarım ─► [4] Eksik Bilgi ─► [5] Mevzuat (BM25)                  │
│ [6] Önceliklendirme ─► [7] Özet ─► [8] KVKK Anonimleştirme                  │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
  ◇ KAPI 2: dil Türkçe mi? ── hayır ──► taslak adımı atlanır
        │ evet
┌── GÖREV 2 · Resmî Yazı Taslaklama ve Yönlendirme ───────────────────────────┐
│ [9] Yazı Taslağı + format denetimi                                          │
│ [10] Birim Yönlendirme ── ◇ KAPI 3b: güven düşükse insan onayı              │
│ [11] Kullanıcı Bilgilendirme + eksik bilgi talepleri                        │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
Kayıt Defteri (SQLite denetim izi) · e-Yazışma üstverisi · HTML işlem raporu
""".strip("\n"),
        language=None,
    )
    st.caption(
        "Orkestratör tüm hattı yönetir: her adımın süresi ve güveni izlenir, "
        "kapı kararları işlem adımlarına şeffaf biçimde kaydedilir."
    )

    st.subheader("Şartname Görev Eşleşmesi")
    g1, g2 = st.columns(2)
    with g1:
        st.markdown(
            "**Görev 1 — Evrak Sınıflandırma ve İçerik Analizi**\n"
            "- Evrakı OCR veya doğrudan metin olarak okuma\n"
            "- Evrak türünü belirleme (dilekçe, üst yazı, tutanak...)\n"
            "- Önemli bilgi unsurlarını çıkarma\n"
            "- **Eksik** bilgi unsurlarını tespit etme\n"
            "- İlgili mevzuat / yazışma kuralı önerme\n"
            "- Kısa özet üretme"
        )
    with g2:
        st.markdown(
            "**Görev 2 — Resmî Yazı Taslaklama ve Birim Yönlendirme**\n"
            "- Üst yazı / cevap / bilgilendirme taslağı üretme\n"
            "- Resmî üslup ve format denetimi\n"
            "- Doğru birime yönlendirme önerisi\n"
            "- Kullanıcıya süreç bilgilendirmesi\n"
            "- Gerekli durumda eksik bilgi **talebi**"
        )

    st.subheader("Veri Kullanımı Notu")
    st.info(
        "Bu sistemde **gerçek kamu verisi kullanılmamaktadır**. Tüm demo evrakları, "
        "yarışma senaryosu için üretilmiş **kurgusal** örneklerdir; kişisel veri içermez. "
        "Sistem çevrimdışı (LLM'siz) modda da uçtan uca çalışacak şekilde tasarlanmıştır."
    )
    st.caption("TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması, 1. Senaryo (Kamu Evrak Süreçleri)")


# ---------------------------------------------------------------------------
# Ana akış
# ---------------------------------------------------------------------------

def main() -> None:
    """Streamlit uygulama ana akışı."""
    st.set_page_config(
        page_title="Kamu Evrak Akıllı Ajan",
        page_icon="🏛️",
        layout="wide",
    )

    st.title("🏛️ Kamu Evrak Akıllı Ajan Sistemi")
    st.caption(
        "Kamu evrak ve yazışma süreçleri için akıllı agent destek sistemi — "
        "evrak sınıflandırma, içerik analizi, resmî yazı taslaklama ve birim yönlendirme."
    )

    # Pipeline kurulumu (önbellekli — bir kez)
    try:
        pipeline = _pipeline_kur()
    except Exception as exc:
        logger.error(f"Pipeline kurulamadı: {exc}")
        st.error(
            f"Sistem başlatılamadı: {exc}\n\n"
            "Bağımlılıkların kurulu olduğundan emin olun: `pip install -r requirements.txt`"
        )
        st.stop()
        return

    # ------------------------------------------------------------------
    # Kenar çubuğu: sistem durumu + mod seçimi + proje künyesi
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Sistem Durumu")

        llm = _llm_bilgisi()
        if llm["aktif"]:
            st.success(f"**LLM backend:** `{llm['backend']}`" + (f"\n\nModel: `{llm['model']}`" if llm["model"] else ""))
        else:
            st.info(
                "**LLM backend:** `offline` → **kural tabanlı mod**\n\n"
                "LLM erişimi yok; tüm ajanlar kural tabanlı yedek yöntemlerle "
                "tam işlevli çalışıyor."
            )

        ajan_sayisi = len(getattr(pipeline.orchestrator, "agents", {}) or {})
        st.metric(
            "Yüklü ajan sayısı", f"{ajan_sayisi} + orkestratör",
            help="Orkestratörün koordine ettiği uzman ajan sayısı — her ajan tek bir "
                 "görevden sorumludur (OCR, sınıflandırma, taslak, yönlendirme...).",
        )

        st.divider()
        mode = st.radio(
            "🎛️ Çalışma modu",
            options=["full", "classify", "draft"],
            format_func=lambda m: MOD_ACIKLAMALARI.get(m, m),
        )

        st.divider()
        st.markdown(
            "**🚀 TEKNOFEST 2026**\n\n"
            "Yapay Zeka Dil Ajanları Yarışması\n\n"
            "*1. Senaryo: Kamu Evrak ve Yazışma Süreçleri için "
            "Akıllı Agent Destek Sistemi*"
        )

    # ------------------------------------------------------------------
    # Sekmeler
    # ------------------------------------------------------------------
    sekme1, sekme2, sekme3, sekme4, sekme5 = st.tabs(
        ["📄 Evrak İşle", "🎬 Demo Evrakları", "📊 Kurum Kokpiti", "🗂️ Kayıt Defteri", "ℹ️ Hakkında"]
    )

    with sekme1:
        _sekme_evrak_isle(pipeline, mode)

    with sekme2:
        _sekme_demo(pipeline, mode)

    with sekme3:
        _sekme_kokpit(pipeline)

    with sekme4:
        _sekme_kayit_defteri(pipeline)

    with sekme5:
        _sekme_hakkinda()


if __name__ == "__main__":
    main()
