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

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

# `streamlit run src/app.py` çağrısında sys.path'e yalnızca src/ eklenir;
# `from src....` import'larının çalışması için proje kökünü ekle.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

logger = logging.getLogger("kamu_evrak_ajan.app")

# ---------------------------------------------------------------------------
# Sabitler (proje geneli sözlüklerle tutarlı)
# ---------------------------------------------------------------------------

DEMO_EVRAK_DIZINI = _PROJECT_ROOT / "data" / "raw" / "kurgu_evraklar"

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


# ---------------------------------------------------------------------------
# Kaynak yükleme (bir kez kurulur)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Ajanlar yükleniyor...")
def _pipeline_kur():
    """Uçtan uca pipeline'ı bir kez kurar ve önbelleğe alır."""
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    return EndToEndPipeline()


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


# ---------------------------------------------------------------------------
# İşleme yardımcıları
# ---------------------------------------------------------------------------

def _dosya_isle(pipeline: Any, dosya_yolu: str, mode: str) -> dict:
    """Dosyayı pipeline üzerinden işler ve toplam süreyi garanti eder."""
    baslangic = time.time()
    sonuc = pipeline.process(dosya_yolu, mode=mode)
    sonuc.setdefault("islem_suresi_saniye", round(time.time() - baslangic, 2))
    return sonuc


def _metin_isle(pipeline: Any, metin: str, mode: str) -> dict:
    """Doğrudan metin girişini orkestratör üzerinden işler."""
    baslangic = time.time()
    sonuc = pipeline.orchestrator.process_text(metin, mode=mode)
    sonuc.setdefault("islem_suresi_saniye", round(time.time() - baslangic, 2))
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
    k1.metric("Evrak Türü", tur, f"güven {tur_guven}" if tur_guven != "—" else None, delta_color="off")
    k2.metric("Önerilen Birim", birim, f"güven {birim_guven}" if birim_guven != "—" else None, delta_color="off")
    k3.metric("Toplam Süre", sure_metni)
    k4.metric("Format Skoru", skor_metni)


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
        with st.expander(f"{i}. {baslik}  ({_fmt_yuzde(benzerlik)} benzerlik)"):
            if benzerlik is not None:
                st.progress(_oran_0_1(benzerlik))
            if kayit.get("icerik_ozeti"):
                st.markdown(str(kayit["icerik_ozeti"]))
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
    st.code(taslak, language=None)
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
            st.markdown(f"{isaret} {ad}" + (f" — _{detay}_" if detay else ""))
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
        satirlar.append({
            "Ajan": adim.get("agent", "—"),
            "Adım": adim.get("description", "—"),
            "Durum": "✅ Başarılı" if durum == "success" else f"❌ {adim.get('error', 'Hata')}",
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


def _sonuclari_goster(sonuc: dict, key_prefix: str) -> None:
    """Tüm sonuç bölümlerini düzenli bir yerleşimle çizer."""
    _metrik_satiri(sonuc)
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

    st.divider()
    _bolum_islem_adimlari(sonuc)


# ---------------------------------------------------------------------------
# Sekmeler
# ---------------------------------------------------------------------------

def _sekme_evrak_isle(pipeline: Any, mode: str) -> None:
    """Sekme 1: dosya yükleme veya doğrudan metin girişi ile evrak işleme."""
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
                with st.spinner("Evrak işleniyor... (OCR → analiz → taslak → yönlendirme)"):
                    fd, gecici_yol = tempfile.mkstemp(suffix=uzanti, prefix="evrak_")
                    with os.fdopen(fd, "wb") as f:
                        f.write(dosya.getbuffer())
                    yeni_sonuc = _dosya_isle(pipeline, gecici_yol, mode)
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
                    with st.spinner("Evrak işleniyor... (analiz → taslak → yönlendirme)"):
                        yeni_sonuc = _metin_isle(pipeline, metin, mode)
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
                with st.spinner(f"'{secilen.name}' işleniyor..."):
                    sonuc = _dosya_isle(pipeline, str(secilen), mode)
                    st.session_state["sonuc_demo"] = sonuc
            except Exception as exc:
                logger.error(f"Demo evrak işleme hatası: {exc}")
                st.error(f"Demo evrak işlenirken bir sorun oluştu: {exc}")

    sonuc = st.session_state.get("sonuc_demo")
    if sonuc:
        st.divider()
        st.success(f"İşlem tamamlandı: **{Path(str(sonuc.get('input_file', ''))).name}**")
        _sonuclari_goster(sonuc, key_prefix="demo")


def _sekme_hakkinda() -> None:
    """Sekme 3: mimari özeti, görev eşleşmesi ve veri kullanımı notu."""
    st.subheader("Mimari Özeti")
    st.markdown(
        "Sistem, bir **orkestratör** tarafından koordine edilen **9 uzman ajandan** oluşur. "
        "Her ajan paylaşılan durum nesnesini (`AgentState`) okuyup kendi alanlarını doldurur; "
        "LLM erişilemezse tüm ajanlar **kural tabanlı** yedek yollarla tam işlevli çalışır."
    )
    st.markdown(
        """
| # | Ajan | Görevi | Şartname Görevi |
|---|------|--------|-----------------|
| 1 | OCR Agent | PDF/görüntü/metinden metin çıkarımı | Görev 1 |
| 2 | Classification Agent | Evrak türü belirleme (kural + LLM eskalasyon) | Görev 1 |
| 3 | Info Extraction Agent | Tarih, kurum, kişi, sayı, konu, muhatap çıkarımı | Görev 1 |
| 4 | Missing Info Agent | Eksik bilgi unsurlarının tespiti | Görev 1 |
| 5 | Legislation Agent | İlgili mevzuat / yazışma kuralı önerisi | Görev 1 |
| 6 | Summarization Agent | Kısa evrak özeti | Görev 1 |
| 7 | Draft Writer Agent | Resmî yazı taslağı + format denetimi | Görev 2 |
| 8 | Routing Agent | Doğru birime yönlendirme önerisi | Görev 2 |
| 9 | User Info Agent | Süreç bilgilendirmesi + eksik bilgi talebi | Görev 2 |
| — | Orchestrator | Akış koordinasyonu, süre/güven izleme | Görev 1 + 2 |
"""
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
        st.metric("Yüklü ajan sayısı", f"{ajan_sayisi} + orkestratör")

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
    sekme1, sekme2, sekme3 = st.tabs(["📄 Evrak İşle", "🎬 Demo Evrakları", "ℹ️ Hakkında"])

    with sekme1:
        _sekme_evrak_isle(pipeline, mode)

    with sekme2:
        _sekme_demo(pipeline, mode)

    with sekme3:
        _sekme_hakkinda()


if __name__ == "__main__":
    main()
