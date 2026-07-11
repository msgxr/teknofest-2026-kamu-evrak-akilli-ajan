"""
İşlem Denetim Raporu — tek evrak için kendine yeten HTML rapor üretimi.

Kamu evrak süreçlerinde bir evrak üzerinde yapılan işlemlerin yazılı ve
arşivlenebilir biçimde raporlanması, denetim ve hesap verebilirliğin
gereğidir (evrak kayıt/denetim izi pratiği; bkz. src/utils/kayit_defteri).
Bu modül, uçtan uca pipeline'ın tek evrak sonucunu — sınıflandırma,
bilgi çıkarımı, eksik bilgiler, mevzuat önerileri, özet, yazı taslağı,
format denetimi, birim yönlendirme, önceliklendirme, KVKK maskeleme
raporu ve adım süreleri — kurumsal görünümlü tek bir HTML dosyasına döker.

Şartname Referansı:
    - Görev 1 + Görev 2 çıktılarının bütüncül sunumu; "gerçek zamana
      yakın çalışma" kanıtı olarak adım süreleri tablosu raporda yer alır.

Tasarım:
    - Çıktı kendine yetendir (inline CSS, dış kaynak yok): rapor dosyası
      internetsiz ortamda ve arşivde tek başına açılabilir.
    - GÜVENLİK (XSS, CWE-79): evrak metninden türeyen TÜM değerler
      html.escape ile kaçırılır; rapor güvenilmeyen içerik taşısa da
      tarayıcıda betik çalıştıramaz.
    - Eksik/boş alanlara toleranslıdır: bölüm verisi yoksa "üretilemedi"
      notu düşülür, rapor asla yarım kalmaz.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kamu_evrak_ajan.islem_raporu")

RAPOR_BASLIGI = "EVRAK İŞLEM DENETİM RAPORU"

# Okunur alan etiketleri (arayüzle tutarlı)
_ALAN_ETIKETLERI = {
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

_ONCELIK_SINIFLARI = {
    "cok_ivedi": ("ÇOK İVEDİ", "kirmizi"),
    "çok ivedi": ("ÇOK İVEDİ", "kirmizi"),
    "ivedi": ("İVEDİ", "kirmizi"),
    "gunlu": ("GÜNLÜ", "turuncu"),
    "günlü": ("GÜNLÜ", "turuncu"),
    "normal": ("Normal", "yesil"),
}

_STIL = """
  body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         color: #1c2733; background: #eef1f5; margin: 0; padding: 24px; }
  .sayfa { max-width: 860px; margin: 0 auto; background: #ffffff;
           border: 1px solid #d5dbe3; border-radius: 6px; overflow: hidden; }
  header { background: #1f3c5f; color: #ffffff; padding: 22px 28px; }
  header h1 { margin: 0 0 4px 0; font-size: 20px; letter-spacing: 0.06em; }
  header p { margin: 0; font-size: 12px; color: #c9d6e6; }
  main { padding: 8px 28px 24px 28px; }
  section { margin-top: 22px; }
  h2 { font-size: 14px; letter-spacing: 0.04em; text-transform: uppercase;
       color: #1f3c5f; border-left: 4px solid #1f3c5f; padding-left: 8px;
       margin: 0 0 10px 0; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border: 1px solid #d5dbe3; padding: 6px 9px; text-align: left;
           vertical-align: top; }
  th { background: #f0f3f7; font-weight: 600; white-space: nowrap; }
  pre { background: #f7f8fa; border: 1px solid #d5dbe3; border-radius: 4px;
        padding: 12px; font-size: 12px; line-height: 1.5;
        white-space: pre-wrap; word-wrap: break-word; overflow-x: auto; }
  ul { margin: 6px 0; padding-left: 20px; font-size: 13px; }
  li { margin: 3px 0; }
  .rozet { display: inline-block; padding: 2px 10px; border-radius: 10px;
           font-size: 12px; font-weight: 600; color: #ffffff; }
  .rozet.kirmizi { background: #b3261e; }
  .rozet.turuncu { background: #b26a00; }
  .rozet.yesil { background: #2e7d32; }
  .rozet.gri { background: #5f6b7a; }
  .not { color: #5f6b7a; font-size: 12px; margin: 6px 0 0 0; }
  .uyari { background: #fdf3e3; border: 1px solid #e8c98a; border-radius: 4px;
           padding: 10px 12px; font-size: 13px; margin: 8px 0; }
  .basarili { color: #2e7d32; font-weight: 600; }
  .basarisiz { color: #b3261e; font-weight: 600; }
  footer { border-top: 1px solid #d5dbe3; padding: 12px 28px; font-size: 11px;
           color: #5f6b7a; background: #f7f8fa; }
  @media print { body { background: #ffffff; padding: 0; }
                 .sayfa { border: none; } }
"""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _e(deger: Any) -> str:
    """Değeri HTML'e güvenli metne çevirir (GÜVENLİK: XSS/CWE-79 kaçışı)."""
    return html.escape(str(deger if deger is not None else "—"), quote=True)


def _sozluk(deger: Any) -> dict:
    """Değeri sözlüğe indirger; sözlük değilse boş sözlük döndürür."""
    return deger if isinstance(deger, dict) else {}


def _yuzde(deger: Any) -> str:
    """Güven/benzerlik skorunu %XX metnine çevirir (0-1 veya 0-100 girdili)."""
    try:
        v = float(deger)
    except (TypeError, ValueError):
        return "—"
    if v <= 1.0:
        v *= 100
    return f"%{v:.0f}"


def _deger_metni(deger: Any) -> str:
    """Çıkarılan bilgi değerini tablo hücresi metnine çevirir."""
    if deger is None:
        return "—"
    if isinstance(deger, str):
        return deger.strip() or "—"
    if isinstance(deger, (list, tuple, set)):
        parcalar = [str(p).strip() for p in deger if str(p).strip()]
        return ", ".join(parcalar) if parcalar else "—"
    return str(deger)


def _alan_adi(anahtar: str) -> str:
    """Alan anahtarını okunur Türkçe etikete çevirir."""
    return _ALAN_ETIKETLERI.get(anahtar, str(anahtar).replace("_", " ").title())


def _bolum(baslik: str, icerik_html: str) -> str:
    """Başlıklı rapor bölümü üretir (başlık sabit metindir, kaçırılır yine)."""
    return f"<section><h2>{_e(baslik)}</h2>{icerik_html}</section>"


def _anahtar_deger_tablosu(satirlar: "list[tuple[str, str]]") -> str:
    """[(etiket, kaçırılmış html değer)] listesinden iki sütunlu tablo üretir.

    Dikkat: değerler çağıran tarafından kaçırılmış olmalıdır (rozet gibi
    güvenli HTML parçaları içerebilir); etiketler burada kaçırılır.
    """
    hucreler = "".join(
        f"<tr><th>{_e(etiket)}</th><td>{deger}</td></tr>" for etiket, deger in satirlar
    )
    return f"<table>{hucreler}</table>"


def _oncelik_rozeti(oncelik: Any) -> str:
    """Öncelik düzeyini renkli rozet HTML'ine çevirir."""
    kod = str(oncelik or "").strip().lower()
    ad, sinif = _ONCELIK_SINIFLARI.get(kod, (kod or "—", "gri"))
    return f'<span class="rozet {sinif}">{_e(ad)}</span>'


# ---------------------------------------------------------------------------
# Bölüm üreticileri
# ---------------------------------------------------------------------------

def _bolum_kunye(sonuc: dict) -> str:
    """Rapor künyesi: kaynak, zaman, süre, insan onayı durumu."""
    insan_onayi = _sozluk(sonuc.get("insan_onayi"))
    onay_gerekli = insan_onayi.get("gerekli") is True
    onay_html = (
        '<span class="rozet turuncu">İNSAN ONAYI GEREKLİ</span>'
        if onay_gerekli
        else '<span class="rozet yesil">Otomatik işlem yeterli</span>'
    )
    sure = sonuc.get("islem_suresi_saniye")
    sure_metni = f"{float(sure):.2f} saniye" if isinstance(sure, (int, float)) else "—"

    icerik = _anahtar_deger_tablosu([
        ("Kaynak Evrak", _e(Path(str(sonuc.get("input_file") or "—")).name)),
        ("Rapor Zamanı", _e(datetime.now().strftime("%d.%m.%Y %H:%M:%S"))),
        ("Toplam İşlem Süresi", _e(sure_metni)),
        ("İnsan Onayı", onay_html),
    ])
    gerekceler = insan_onayi.get("gerekceler") or []
    if onay_gerekli and gerekceler:
        maddeler = "".join(f"<li>{_e(g)}</li>" for g in gerekceler)
        icerik += f'<div class="uyari"><strong>Onay gerekçeleri:</strong><ul>{maddeler}</ul></div>'
    return _bolum("İşlem Künyesi", icerik)


def _bolum_siniflandirma(sonuc: dict) -> str:
    """Görev 1: evrak türü sınıflandırma sonucu."""
    sinif = _sozluk(sonuc.get("siniflandirma"))
    if not sinif:
        return _bolum("Sınıflandırma", '<p class="not">Sınıflandırma sonucu üretilemedi.</p>')
    icerik = _anahtar_deger_tablosu([
        ("Evrak Türü", f"{_e(sinif.get('tur_adi') or sinif.get('tur'))} (<code>{_e(sinif.get('tur'))}</code>)"),
        ("Güven", _e(_yuzde(sinif.get("guven")))),
        ("Yöntem", _e(sinif.get("yontem") or "—")),
        ("Açıklama", _e(sinif.get("aciklama") or "—")),
    ])
    return _bolum("Sınıflandırma", icerik)


def _bolum_cikarim(sonuc: dict) -> str:
    """Görev 1: çıkarılan bilgi unsurları tablosu."""
    bilgiler = _sozluk(sonuc.get("bilgi_cikarim"))
    if not bilgiler:
        return _bolum("Çıkarılan Bilgiler", '<p class="not">Çıkarılabilen bilgi unsuru bulunamadı.</p>')
    satirlar = [(_alan_adi(anahtar), _e(_deger_metni(deger))) for anahtar, deger in bilgiler.items()]
    return _bolum("Çıkarılan Bilgiler", _anahtar_deger_tablosu(satirlar))


def _bolum_eksikler(sonuc: dict) -> str:
    """Görev 1 + 2: eksik bilgi tespitleri ve eksik bilgi talepleri."""
    eksikler = sonuc.get("eksik_bilgiler") or []
    talepler = sonuc.get("eksik_bilgi_talepleri") or []
    parcalar = []
    if not eksikler:
        parcalar.append('<p class="not">Evrakta kritik bir eksik bilgi tespit edilmedi.</p>')
    else:
        hucreler = []
        for eksik in eksikler:
            if not isinstance(eksik, dict):
                hucreler.append(f"<tr><td>—</td><td>{_e(eksik)}</td><td>—</td></tr>")
                continue
            hucreler.append(
                f"<tr><td>{_e((eksik.get('oncelik') or 'bilgi')).upper()}</td>"
                f"<td>{_e(_alan_adi(str(eksik.get('alan', '—'))))}</td>"
                f"<td>{_e(eksik.get('aciklama') or '—')}"
                + (f"<br><em>Öneri: {_e(eksik['oneri'])}</em>" if eksik.get("oneri") else "")
                + "</td></tr>"
            )
        parcalar.append(
            "<table><tr><th>Öncelik</th><th>Alan</th><th>Açıklama</th></tr>"
            + "".join(hucreler) + "</table>"
        )
    if talepler:
        maddeler = []
        for talep in talepler:
            if isinstance(talep, dict):
                metin = _e(talep.get("soru") or talep.get("alan") or "—")
                if talep.get("gerekce"):
                    metin += f' <span class="not">({_e(talep["gerekce"])})</span>'
                maddeler.append(f"<li>{metin}</li>")
            else:
                maddeler.append(f"<li>{_e(talep)}</li>")
        parcalar.append(
            "<p class='not'><strong>Eksik bilgi talepleri:</strong></p><ul>"
            + "".join(maddeler) + "</ul>"
        )
    return _bolum("Eksik Bilgiler", "".join(parcalar))


def _bolum_mevzuat(sonuc: dict) -> str:
    """Görev 1: ilgili mevzuat / yazışma kuralı önerileri."""
    eslesmeler = sonuc.get("mevzuat_eslestirme") or []
    if not eslesmeler:
        return _bolum("Mevzuat Önerileri", '<p class="not">Bu evrak için mevzuat önerisi üretilemedi.</p>')
    hucreler = []
    for kayit in eslesmeler:
        if not isinstance(kayit, dict):
            hucreler.append(f"<tr><td>{_e(kayit)}</td><td>—</td><td>—</td></tr>")
            continue
        hucreler.append(
            f"<tr><td>{_e(kayit.get('baslik') or '—')}</td>"
            f"<td>{_e(_yuzde(kayit.get('benzerlik')))}</td>"
            f"<td>{_e(kayit.get('icerik_ozeti') or kayit.get('kaynak') or '—')}</td></tr>"
        )
    tablo = (
        "<table><tr><th>Mevzuat</th><th>Benzerlik</th><th>İçerik Özeti</th></tr>"
        + "".join(hucreler) + "</table>"
    )
    return _bolum("Mevzuat Önerileri", tablo)


def _bolum_ozet(sonuc: dict) -> str:
    """Görev 1: evrak özeti."""
    ozet = str(sonuc.get("ozet") or "").strip()
    if not ozet:
        return _bolum("Özet", '<p class="not">Özet üretilemedi.</p>')
    return _bolum("Özet", f"<pre>{_e(ozet)}</pre>")


def _bolum_taslak(sonuc: dict) -> str:
    """Görev 2: üretilen resmî yazı taslağı."""
    taslak = str(sonuc.get("yazi_taslagi") or "").strip()
    if not taslak:
        return _bolum("Yazı Taslağı", '<p class="not">Yazı taslağı üretilmedi (mod veya koşullu kapı nedeniyle).</p>')
    tur = str(sonuc.get("yazi_turu") or "taslak")
    return _bolum(
        "Yazı Taslağı",
        f'<p class="not">Taslak türü: <strong>{_e(tur)}</strong></p><pre>{_e(taslak)}</pre>',
    )


def _bolum_format(sonuc: dict) -> str:
    """Görev 2: resmî yazışma format denetimi kontrol listesi."""
    denetim = _sozluk(sonuc.get("format_denetimi"))
    if not denetim:
        return _bolum("Format Denetimi", '<p class="not">Format denetimi sonucu bulunmuyor.</p>')
    uygun = denetim.get("uygun")
    durum = (
        '<span class="basarili">Resmî yazışma kurallarına uygun</span>' if uygun is True
        else '<span class="basarisiz">İyileştirme gereken noktalar var</span>' if uygun is False
        else "—"
    )
    parcalar = [_anahtar_deger_tablosu([
        ("Genel Durum", durum),
        ("Format Skoru", _e(_yuzde(denetim.get("skor")))),
    ])]
    kontroller = denetim.get("kontroller") or []
    if kontroller:
        maddeler = []
        for kontrol in kontroller:
            if isinstance(kontrol, dict):
                ad = (
                    kontrol.get("kural") or kontrol.get("kontrol") or kontrol.get("ad")
                    or kontrol.get("baslik") or kontrol.get("aciklama") or str(kontrol)
                )
                gecti = kontrol.get(
                    "gecti",
                    kontrol.get("uygun", kontrol.get("sonuc", kontrol.get("durum"))),
                )
                isaret = '<span class="basarili">✓</span>' if gecti else '<span class="basarisiz">✗</span>'
                detay = kontrol.get("detay") or kontrol.get("mesaj") or ""
                dayanak = kontrol.get("dayanak") or ""
                madde = f"<li>{isaret} {_e(ad)}"
                if detay:
                    madde += f" — <em>{_e(detay)}</em>"
                if dayanak:
                    # Denetim kuralının yönetmelik dayanağı (madde/fıkra)
                    madde += f' <span class="not">[{_e(dayanak)}]</span>'
                maddeler.append(madde + "</li>")
            else:
                maddeler.append(f"<li>{_e(kontrol)}</li>")
        parcalar.append("<ul>" + "".join(maddeler) + "</ul>")
    return _bolum("Format Denetimi", "".join(parcalar))


def _bolum_yonlendirme(sonuc: dict) -> str:
    """Görev 2: birim yönlendirme önerisi ve alternatifler."""
    yonlendirme = _sozluk(sonuc.get("yonlendirme"))
    if not yonlendirme:
        return _bolum("Birim Yönlendirme", '<p class="not">Yönlendirme önerisi üretilemedi.</p>')
    satirlar = [
        ("Önerilen Birim", _e(yonlendirme.get("birim") or "—")),
        ("Birim Kodu", f"<code>{_e(yonlendirme.get('birim_kodu') or '—')}</code>"),
        ("Güven", _e(_yuzde(yonlendirme.get("guven")))),
        ("Gerekçe", _e(yonlendirme.get("gerekce") or "—")),
    ]
    alternatifler = yonlendirme.get("alternatifler") or []
    if alternatifler:
        adlar = []
        for alt in alternatifler:
            if isinstance(alt, dict):
                adlar.append(f"{alt.get('birim', '—')} ({_yuzde(alt.get('skor', alt.get('guven')))})")
            else:
                adlar.append(str(alt))
        satirlar.append(("Alternatif Birimler", _e(", ".join(adlar))))
    return _bolum("Birim Yönlendirme", _anahtar_deger_tablosu(satirlar))


def _bolum_oncelik(sonuc: dict) -> str:
    """Yenilik modülü: aciliyet/yasal süre önceliklendirmesi."""
    oncelik_bilgisi = _sozluk(sonuc.get("onceliklendirme"))
    if not oncelik_bilgisi:
        return _bolum("Önceliklendirme", '<p class="not">Önceliklendirme sonucu bulunmuyor.</p>')
    son_tarih = (
        oncelik_bilgisi.get("son_tarih")
        or oncelik_bilgisi.get("son_islem_tarihi")
        or oncelik_bilgisi.get("termin_tarihi")
    )
    satirlar = [
        ("Öncelik", _oncelik_rozeti(oncelik_bilgisi.get("oncelik"))),
        ("Son İşlem Tarihi", _e(son_tarih or "—")),
        ("Kalan Gün", _e(oncelik_bilgisi.get("kalan_gun") if oncelik_bilgisi.get("kalan_gun") is not None else "—")),
        ("Gerekçe", _e(oncelik_bilgisi.get("gerekce") or oncelik_bilgisi.get("aciklama") or "—")),
    ]
    return _bolum("Önceliklendirme", _anahtar_deger_tablosu(satirlar))


def _bolum_kvkk(sonuc: dict) -> str:
    """Yenilik modülü: KVKK anonimleştirme/maskeleme raporu."""
    anonim = _sozluk(sonuc.get("anonimlestirme"))
    rapor = _sozluk(anonim.get("rapor") or anonim.get("maskeleme_raporu") or anonim.get("anonymization_report"))
    if not rapor:
        return _bolum("KVKK Maskeleme Raporu", '<p class="not">Maskeleme raporu bulunmuyor.</p>')
    satirlar = [("Toplam Maskelenen Unsur", _e(rapor.get("toplam", 0)))]
    maskelenen = _sozluk(rapor.get("maskelenen"))
    for kategori, adet in maskelenen.items():
        satirlar.append((_alan_adi(str(kategori)), _e(adet)))
    icerik = _anahtar_deger_tablosu(satirlar)
    icerik += (
        '<p class="not">Kişisel veriler maskelenmiş paylaşım nüshası ayrıca üretilmiştir; '
        "kurum dışı paylaşımlarda maskeli nüsha kullanılmalıdır (6698 sayılı KVKK bağlamı).</p>"
    )
    return _bolum("KVKK Maskeleme Raporu", icerik)


def _bolum_adimlar(sonuc: dict) -> str:
    """Meta: adım adım süre/durum tablosu (gerçek zamana yakın çalışma kanıtı)."""
    adimlar = sonuc.get("islem_adimlari") or []
    if not adimlar:
        return _bolum("İşlem Adımları", '<p class="not">İşlem adımı kaydı bulunmuyor.</p>')
    hucreler = []
    toplam = 0.0
    for adim in adimlar:
        if not isinstance(adim, dict):
            continue
        try:
            toplam += float(adim.get("sure_saniye", 0.0))
        except (TypeError, ValueError):
            pass
        durum = adim.get("status", "")
        if durum == "success":
            durum_html = '<span class="basarili">Başarılı</span>'
        elif durum == "atlandi":
            durum_html = f"Atlandı — {_e(adim.get('neden') or '')}"
        else:
            durum_html = f'<span class="basarisiz">Hata — {_e(adim.get("error") or "")}</span>'
        sure = adim.get("sure_saniye")
        sure_metni = f"{float(sure):.3f}" if isinstance(sure, (int, float)) else "—"
        hucreler.append(
            f"<tr><td>{_e(adim.get('agent') or '—')}</td>"
            f"<td>{_e(adim.get('description') or '—')}</td>"
            f"<td>{durum_html}</td><td>{_e(sure_metni)}</td></tr>"
        )
    tablo = (
        "<table><tr><th>Ajan</th><th>Adım</th><th>Durum</th><th>Süre (sn)</th></tr>"
        + "".join(hucreler) + "</table>"
        + f'<p class="not">{len(hucreler)} ajan adımı toplam {toplam:.2f} saniyede tamamlandı.</p>'
    )
    return _bolum("İşlem Adımları", tablo)


# ---------------------------------------------------------------------------
# Ana üretici
# ---------------------------------------------------------------------------

def uret_html_rapor(sonuc: dict) -> str:
    """
    Tek evrakın işlem sonucunu kendine yeten HTML denetim raporuna döker.

    Args:
        sonuc: EndToEndPipeline.process/process_text çıktısı sözlük.
            Eksik anahtarlara toleranslıdır.

    Returns:
        Tam HTML belge metni (UTF-8; inline CSS, dış kaynak yok).
    """
    sonuc = _sozluk(sonuc)
    bolumler = "".join([
        _bolum_kunye(sonuc),
        _bolum_siniflandirma(sonuc),
        _bolum_cikarim(sonuc),
        _bolum_eksikler(sonuc),
        _bolum_mevzuat(sonuc),
        _bolum_ozet(sonuc),
        _bolum_taslak(sonuc),
        _bolum_format(sonuc),
        _bolum_yonlendirme(sonuc),
        _bolum_oncelik(sonuc),
        _bolum_kvkk(sonuc),
        _bolum_adimlar(sonuc),
    ])
    logger.info(f"HTML işlem raporu üretildi: {sonuc.get('input_file') or 'evrak'}")
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(RAPOR_BASLIGI)}</title>
<style>{_STIL}</style>
</head>
<body>
<div class="sayfa">
<header>
<h1>{_e(RAPOR_BASLIGI)}</h1>
<p>Kamu Evrak Akıllı Ajan Sistemi — TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (kurgusal demo verisi)</p>
</header>
<main>
{bolumler}
</main>
<footer>
Bu rapor sistem tarafından otomatik üretilmiştir; gerçek kamu verisi içermez.
Düşük güvenli kararlar için insan onayı bölümündeki uyarılar dikkate alınmalıdır.
</footer>
</div>
</body>
</html>
"""
