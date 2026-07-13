# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Demo Senaryosu 2.0 — Jüri sunumu için 4 sahneli uçtan uca gösterim.

Sahneler (şartname m.8: temel yetenekler ve özgün çıktılar gözlemlenebilir):
    1. Vatandaş dilekçesi → analiz + CEVAP TASLAĞI (Görev 1 + Görev 2)
    2. İVEDİ damgalı üst yazı → TRİYAJ (yasal süre/son işlem tarihi)
       + BİRİM YÖNLENDİRME (çalışma anında bugünün tarihiyle üretilir;
       kalan gün hesabı canlı demoda her zaman anlamlı kalır)
    3. Taranmış/gürültülü evrak görüntüsü → OCR hattı (opsiyonel yığın
       kuruluysa çalışır; değilse dürüst mesajla atlanır — G1-a kanıtı)
    4. "İNTERNETİ KES" sahnesi — tüm ağ soket erişimi programatik olarak
       engellenirken aynı evrak yeniden işlenir: çekirdek kural tabanlı
       sistem kesintisiz sürer (offline-first kanıtı, şartname m.8
       "internet kesintisine karşı yedek plan" tavsiyesinin cevabı)

Kayıt yedeği: `python demo/demo_scenario.py --kayit demo_kaydi.txt`
konsol dökümünü dosyaya kaydeder (jüri kayıttan izleme talebine yedek).
Süre provası: demo sonunda toplam süre, 4 dakikalık hedefle karşılaştırılır.
"""

import argparse
import socket
import sys
import time
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Proje kök dizinini path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# TAŞINABİLİRLİK: Windows'ta stdout UTF-8 değilse (Türkçe konsol cp1254 veya
# çıktı dosyaya/pipe'a yönlendirildiğinde) rich çıktısındaki emoji/Türkçe
# karakterler UnicodeEncodeError ile çöker. stdout/stderr'i UTF-8'e sabitleyerek
# demo komutunun her ortamda çalışmasını garanti et (demo/README'deki elle
# PYTHONIOENCODING geçici çözümünü gereksiz kılar); errors="replace" zarif düşüş.
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(record=True)

# Demo hedef süresi (10 dakikalık sunumda demoya ayrılan pay)
DEMO_HEDEF_SANIYE = 240

# Çalışma anında üretilen demo girdileri bu dizine yazılır
DEMO_GIRDI_DIZINI = project_root / "demo" / "demo_evraklar"

# İVEDİ damgalı üst yazı şablonu: tarih çalışma anında doldurulur ki
# triyajın "kalan gün" hesabı canlı demoda her zaman ileriye baksın
IVEDI_SABLONU = """T.C.
AKÇOVA VALİLİĞİ
İl Afet Koordinasyon Birimi

                                    İVEDİ

Sayı  : E-58231467-249.05-2026/641
Konu  : Sel riski taşıyan bölgelerde acil tahliye planı güncellemesi
Tarih : {tarih}

AKÇOVA BELEDİYE BAŞKANLIĞINA

İlgi : a) İl Afet Koordinasyon Kurulunun {ilgi_tarih} tarihli kararı.

Meteoroloji verilerine göre önümüzdeki hafta il genelinde kuvvetli yağış
beklenmektedir. İlgi karar uyarınca, dere yatağına yakın mahallelerdeki
acil tahliye planlarının güncellenmesi ve toplanma alanı işaretlemelerinin
denetlenmesi gerekmektedir.

Söz konusu güncellemelerin 5 iş günü içinde tamamlanarak sonucundan
Valiliğimize bilgi verilmesini önemle arz ederim.

                                                        (e-imzalıdır)
                                                        Vali a.
                                                        Vali Yardımcısı
"""


def _ivedi_evrak_uret() -> Path:
    """İVEDİ üst yazıyı bugünün tarihiyle üretip yoluna döndürür."""
    DEMO_GIRDI_DIZINI.mkdir(parents=True, exist_ok=True)
    bugun = date.today()
    icerik = IVEDI_SABLONU.format(
        tarih=bugun.strftime("%d.%m.%Y"),
        ilgi_tarih=(bugun - timedelta(days=3)).strftime("%d.%m.%Y"),
    )
    yol = DEMO_GIRDI_DIZINI / "ivedi_ust_yazi.txt"
    yol.write_text(icerik, encoding="utf-8")
    return yol


def _taranmis_evrak_uret() -> "Path | None":
    """
    Taranmış görünümlü (hafif eğik + benekli) kurgu dilekçe görüntüsü üretir.

    Pillow kurulu değilse None döner (görüntü sahnesi dürüstçe atlanır);
    üretim her koşulda deterministik tohumla yapılır.
    """
    try:
        import random

        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    metin_kaynagi = project_root / "data" / "raw" / "kurgu_evraklar" / "dilekce_01.txt"
    try:
        metin = metin_kaynagi.read_text(encoding="utf-8")
    except OSError:
        return None

    goruntu = Image.new("L", (1240, 1754), color=245)  # A4 @150dpi, açık gri
    cizim = ImageDraw.Draw(goruntu)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    y = 90
    for satir in metin.splitlines():
        cizim.text((100, y), satir, fill=25, font=font)
        y += 40

    # Tarayıcı izlenimi: hafif eğim + tuz-biber beneği (deterministik)
    rnd = random.Random(2026)
    for _ in range(2600):
        x, yy = rnd.randint(0, 1239), rnd.randint(0, 1753)
        goruntu.putpixel((x, yy), rnd.choice((0, 60, 200, 255)))
    goruntu = goruntu.rotate(1.2, expand=False, fillcolor=245)

    DEMO_GIRDI_DIZINI.mkdir(parents=True, exist_ok=True)
    yol = DEMO_GIRDI_DIZINI / "taranmis_dilekce.png"
    goruntu.save(yol)
    return yol


@contextmanager
def _internet_kesildi():
    """
    Tüm ağ soket erişimini geçici olarak engeller ("interneti kes" sahnesi).

    socket.socket kurucusu istisna fırlatacak biçimde değiştirilir; blok
    çıkışında eski davranış geri yüklenir. Böylece jüriye, sistemin ağ
    tamamen yokken de uçtan uca çalıştığı PROGRAMATİK olarak kanıtlanır.
    """
    orijinal_socket = socket.socket

    class _AgYok(socket.socket):
        def __init__(self, *args, **kwargs):
            raise OSError("Demo: ağ erişimi bilinçli olarak kesildi")

    socket.socket = _AgYok  # type: ignore[misc]
    try:
        yield
    finally:
        socket.socket = orijinal_socket  # type: ignore[misc]


def run_demo(kayit_dosyasi: "str | None" = None) -> None:
    """Demo senaryosunu (4 sahne) çalıştırır."""
    demo_baslangic = time.perf_counter()

    console.print(Panel(
        "[bold cyan]🎬 Demo Senaryosu 2.0[/bold cyan]\n\n"
        "Sahne 1: Vatandaş dilekçesi → analiz + cevap taslağı\n"
        "Sahne 2: İVEDİ üst yazı → triyaj (yasal süre) + yönlendirme\n"
        "Sahne 3: Taranmış görüntü → OCR hattı (opsiyonel yığın)\n"
        "Sahne 4: İNTERNET KESİLİR → sistem kural tabanlı çekirdekle sürer",
        title="TEKNOFEST 2026 — Kamu Evrak Akıllı Ajan",
        border_style="blue",
    ))

    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    pipeline = EndToEndPipeline()

    # ------------------------------------------------------------------
    # Sahne 1 — Dilekçe → cevap taslağı
    # ------------------------------------------------------------------
    _sahne_basligi(1, "Vatandaş dilekçesi → analiz + cevap taslağı")
    dilekce = project_root / "data" / "raw" / "kurgu_evraklar" / "dilekce_01.txt"
    _isle_ve_goster(pipeline, dilekce)

    # ------------------------------------------------------------------
    # Sahne 2 — İVEDİ üst yazı → triyaj + yönlendirme
    # ------------------------------------------------------------------
    _sahne_basligi(2, "İVEDİ damgalı üst yazı → triyaj + birim yönlendirme")
    console.print(
        "[dim]İVEDİ evrak, kalan-gün hesabı canlı kalsın diye bugünün "
        "tarihiyle üretiliyor...[/dim]"
    )
    ivedi = _ivedi_evrak_uret()
    _isle_ve_goster(pipeline, ivedi)

    # ------------------------------------------------------------------
    # Sahne 3 — Taranmış görüntü → OCR
    # ------------------------------------------------------------------
    _sahne_basligi(3, "Taranmış/gürültülü evrak görüntüsü → OCR hattı")
    goruntu = _taranmis_evrak_uret()
    if goruntu is None:
        console.print(Panel(
            "Pillow kurulu olmadığından taranmış görüntü üretilemedi.\n"
            "Kurulum: pip install -r requirements-optional.txt",
            title="ℹ️ Sahne atlandı (dürüst bildirim)", border_style="yellow",
        ))
    else:
        console.print(f"[dim]Kurgu taranmış görüntü üretildi: {goruntu.name}[/dim]")
        try:
            sonuc = pipeline.process(str(goruntu))
            ocr_metni = str((sonuc.get("ocr") or {}).get("metin") or "").strip()
            if not ocr_metni:
                raise RuntimeError("görüntüden metin çıkarılamadı")
            _display_results(sonuc)
        except Exception as e:
            console.print(Panel(
                f"OCR yığını (pytesseract/easyocr) bu kurulumda yok: {e}\n"
                "Çekirdek sistem TXT/PDF ile tam çalışır; görüntü OCR'ı "
                "opsiyoneldir (pip install -r requirements-optional.txt "
                "+ Tesseract kurulumu).",
                title="ℹ️ Sahne atlandı (dürüst bildirim)", border_style="yellow",
            ))

    # ------------------------------------------------------------------
    # Sahne 4 — İnterneti kes: offline devamlılık kanıtı
    # ------------------------------------------------------------------
    _sahne_basligi(4, "İNTERNET KESİLDİ — sistem çalışmaya devam ediyor")
    console.print(Panel(
        "[bold red]Tüm ağ soket erişimi şu anda programatik olarak "
        "ENGELLENDİ.[/bold red]\nAynı İVEDİ evrak, ağ tamamen yokken "
        "yeniden işleniyor...",
        border_style="red",
    ))
    with _internet_kesildi():
        baslangic = time.perf_counter()
        sonuc = pipeline.process(str(ivedi))
        sure = time.perf_counter() - baslangic
    console.print(Panel(
        f"[bold green]✅ Sistem ağ olmadan uçtan uca çalıştı.[/bold green]\n"
        f"Tür: {sonuc.get('siniflandirma', {}).get('tur_adi', '?')} · "
        f"Yönlendirme: {sonuc.get('yonlendirme', {}).get('birim', '?')} · "
        f"Taslak: {'üretildi' if sonuc.get('yazi_taslagi') else 'üretilemedi'}\n"
        f"Süre: {sure:.2f} sn — çekirdek tamamen kural tabanlı, "
        f"hiçbir dış servis çağrısı yok (offline-first).",
        title="🔌 Offline Devamlılık Kanıtı", border_style="green",
    ))

    # ------------------------------------------------------------------
    # Kapanış: süre provası + kayıt
    # ------------------------------------------------------------------
    toplam = time.perf_counter() - demo_baslangic
    durum = "✅ hedefin içinde" if toplam <= DEMO_HEDEF_SANIYE else "⚠️ hedef aşıldı"
    console.print(Panel(
        f"Toplam demo süresi: [bold]{toplam:.1f} sn[/bold] "
        f"(hedef ≤ {DEMO_HEDEF_SANIYE} sn — {durum})",
        title="⏱️ Süre Provası", border_style="cyan",
    ))

    if kayit_dosyasi:
        console.save_text(kayit_dosyasi)
        console.print(f"[dim]Demo kaydı yazıldı: {kayit_dosyasi}[/dim]")


def _sahne_basligi(no: int, baslik: str) -> None:
    console.print()
    console.print(Panel(
        f"[bold]SAHNE {no}[/bold] — {baslik}", border_style="yellow",
    ))


def _isle_ve_goster(pipeline, dosya: Path) -> None:
    """Evrakı işleyip sonuç panellerini basar (hata toleranslı)."""
    if not dosya.exists():
        console.print(f"[red]❌ Dosya bulunamadı: {dosya}[/red]")
        return
    try:
        sonuc = pipeline.process(str(dosya))
        _display_results(sonuc)
    except Exception as e:
        console.print(f"[red]Hata: {e}[/red]")
    console.print("─" * 80)


def _display_results(sonuc: dict) -> None:
    """İşlem sonuçlarını görsel olarak gösterir."""
    # Sınıflandırma
    if sonuc.get("siniflandirma"):
        console.print(Panel(
            f"[bold]Tür:[/bold] {sonuc['siniflandirma'].get('tur_adi', '?')}\n"
            f"[bold]Güven:[/bold] {sonuc['siniflandirma'].get('guven', 0):.0%}",
            title="🏷️ Sınıflandırma",
            border_style="green",
        ))

    # Bilgi çıkarım
    if sonuc.get("bilgi_cikarim"):
        info = sonuc["bilgi_cikarim"]
        info_text = ""
        if info.get("konu"):
            info_text += f"[bold]Konu:[/bold] {info['konu']}\n"
        if info.get("tarihler"):
            info_text += f"[bold]Tarihler:[/bold] {', '.join(info['tarihler'])}\n"
        if info.get("kurum_adlari"):
            info_text += f"[bold]Kurumlar:[/bold] {', '.join(info['kurum_adlari'][:3])}\n"
        if info_text:
            console.print(Panel(info_text.strip(), title="🔍 Bilgi Çıkarım", border_style="blue"))

    # Eksik bilgiler
    if sonuc.get("eksik_bilgiler"):
        eksik_text = "\n".join(
            f"• [{e.get('oncelik', '?').upper()}] {e.get('aciklama', '?')}"
            for e in sonuc["eksik_bilgiler"]
        )
        console.print(Panel(eksik_text, title="⚠️ Eksik Bilgiler", border_style="yellow"))

    # Mevzuat önerileri (madde referansı + gerekçeyle — jüri önünde madde gösterilir)
    if sonuc.get("mevzuat_eslestirme"):
        satirlar = []
        for m in sonuc["mevzuat_eslestirme"][:3]:
            satir = f"• {m.get('baslik', '?')}"
            if m.get("madde_etiketi"):
                satir += f" [bold]({m['madde_etiketi']})[/bold]"
            satir += f" [dim](benzerlik: {m.get('benzerlik', 0):.0%})[/dim]"
            if m.get("gerekce"):
                satir += f"\n  [dim]gerekçe: {m['gerekce'][:90]}[/dim]"
            satirlar.append(satir)
        console.print(Panel("\n".join(satirlar), title="📚 Mevzuat Önerileri", border_style="blue"))

    # Özet
    if sonuc.get("ozet"):
        console.print(Panel(sonuc["ozet"], title="📝 Özet", border_style="cyan"))

    # Yazı taslağı
    if sonuc.get("yazi_taslagi"):
        console.print(Panel(
            sonuc["yazi_taslagi"],
            title=f"✍️ Yazı Taslağı ({sonuc.get('yazi_turu', '?')})",
            border_style="green",
        ))

    # Format denetimi (madde dayanaklarıyla)
    if sonuc.get("format_denetimi"):
        fd = sonuc["format_denetimi"]
        kontrol_text = "\n".join(
            f"{'✅' if k.get('durum') else '❌'} {k.get('kural', '?')}"
            + (f" [dim][{k['dayanak']}][/dim]" if k.get("dayanak") else "")
            for k in fd.get("kontroller", [])
        )
        console.print(Panel(
            f"[bold]Skor:[/bold] {fd.get('skor', 0):.0%}\n{kontrol_text}",
            title="📐 Resmî Yazışma Format Denetimi (madde dayanaklı)",
            border_style="green" if fd.get("uygun") else "yellow",
        ))

    # Bağımsız taslak kalite hakemi
    kalite = sonuc.get("taslak_kalitesi") or {}
    if kalite.get("puan") is not None:
        bilesen = kalite.get("bilesenler", {})
        console.print(Panel(
            f"[bold]Puan:[/bold] {kalite['puan']}/100 "
            f"[dim]({kalite.get('yontem', '?')})[/dim]\n"
            + " · ".join(f"{k}: {v}" for k, v in bilesen.items()),
            title="⚖️ Taslak Kalite Hakemi", border_style="cyan",
        ))

    # Yönlendirme
    if sonuc.get("yonlendirme"):
        y = sonuc["yonlendirme"]
        console.print(Panel(
            f"[bold]Birim:[/bold] {y.get('birim', '?')}\n"
            f"[bold]Güven:[/bold] {y.get('guven', 0):.0%}\n"
            f"[bold]Gerekçe:[/bold] {y.get('gerekce', '?')}",
            title="🏢 Birim Yönlendirme",
            border_style="magenta",
        ))

    # Aciliyet / yasal süre (yenilik: süreli evrak takibi)
    triage = sonuc.get("onceliklendirme") or {}
    if triage.get("oncelik", "normal") != "normal" or triage.get("son_tarih"):
        yasal = triage.get("yasal_sure") or {}
        triage_text = f"[bold]Öncelik:[/bold] {triage.get('oncelik', '?').upper()}"
        if triage.get("son_tarih"):
            triage_text += f"\n[bold]Son işlem tarihi:[/bold] {triage['son_tarih']}"
            if triage.get("kalan_gun") is not None:
                triage_text += f" (kalan: {triage['kalan_gun']} gün)"
        if yasal.get("kaynak"):
            triage_text += f"\n[bold]Dayanak:[/bold] {yasal['kaynak']}"
        console.print(Panel(triage_text, title="⏰ Aciliyet / Yasal Süre", border_style="red"))

    # KVKK paylaşım nüshası (yenilik: kişisel veri maskeleme)
    anonim = sonuc.get("anonimlestirme") or {}
    if anonim.get("rapor", {}).get("toplam"):
        maskeler = anonim["rapor"].get("maskelenen", {})
        ozet_str = ", ".join(f"{k}: {v}" for k, v in maskeler.items() if v)
        console.print(Panel(
            f"[bold]Maskelenen kişisel veri:[/bold] {ozet_str}\n"
            f"[dim]Paylaşım nüshası üretildi (KVKK 6698 sK. bağlamı).[/dim]",
            title="🔒 KVKK Paylaşım Nüshası",
            border_style="blue",
        ))

    # Eksik bilgi talepleri (Görev 2: "gerekli durumlarda eksik bilgi talep edebilmesi")
    if sonuc.get("eksik_bilgi_talepleri"):
        talep_text = "\n".join(
            f"❓ {t.get('soru', '?')}" for t in sonuc["eksik_bilgi_talepleri"]
        )
        console.print(Panel(talep_text, title="💬 Eksik Bilgi Talepleri", border_style="red"))

    # İşlem adımları ve süreleri (gerçek zamana yakın çalışma kanıtı)
    if sonuc.get("islem_adimlari"):
        adim_table = Table(title="⏱️ İşlem Adımları")
        adim_table.add_column("Adım", style="cyan")
        adim_table.add_column("Durum", style="bold")
        adim_table.add_column("Süre (sn)", justify="right")
        for adim in sonuc["islem_adimlari"]:
            durum = "✅" if adim.get("status") == "success" else "❌"
            adim_table.add_row(
                adim.get("description", "?"),
                durum,
                f"{adim.get('sure_saniye', 0):.3f}",
            )
        console.print(adim_table)

    # İşlem süresi
    if sonuc.get("islem_suresi_saniye"):
        console.print(f"\n⏱️  Toplam işlem süresi: {sonuc['islem_suresi_saniye']:.2f} saniye")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TEKNOFEST 2026 Kamu Evrak Akıllı Ajan — 4 sahneli demo"
    )
    parser.add_argument(
        "--kayit", metavar="DOSYA", default=None,
        help="Konsol dökümünü dosyaya kaydet (jüri kayıt yedeği)",
    )
    args = parser.parse_args()
    run_demo(kayit_dosyasi=args.kayit)
