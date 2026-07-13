"""
Ana uygulama giriş noktası.

Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi'ni
başlatır ve uçtan uca evrak işleme pipeline'ını çalıştırır.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.logging import RichHandler

from src.config import settings
from src.pipelines.end_to_end_pipeline import EndToEndPipeline

# TAŞINABİLİRLİK (madde 4/5 — uçtan uca akış kırılamaz, offline çekirdek tam çalışır):
# Windows'ta stdout UTF-8 değilse (Türkçe konsol cp1254 / cp1252 ya da çıktı bir
# dosyaya/pipe'a yönlendirildiğinde) rich banner'ındaki emoji/Türkçe karakterler
# UnicodeEncodeError ile çöker ve dokümante CLI komutu (python -m src.main --input ...)
# hiçbir evrak işlenmeden EXIT 1 verir. stdout/stderr'i UTF-8'e sabitleyerek komutun
# her ortamda (borulama/yönlendirme/legacy konsol dahil) çalışmasını garanti ederiz;
# errors="replace" yeniden yapılandırılamayan akışlarda zarif düşüş sağlar.
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Rich console
console = Console()

# Loglama yapılandırması
logging.basicConfig(
    level=getattr(logging, settings.app.log_level),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("kamu_evrak_ajan")


def print_banner() -> None:
    """Uygulama başlangıç banner'ını gösterir."""
    banner_text = (
        "[bold cyan]🏛️ Kamu Evrak ve Yazışma Süreçleri için[/bold cyan]\n"
        "[bold green]🤖 Akıllı Agent Destek Sistemi[/bold green]\n"
        "[dim]TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması[/dim]"
    )
    console.print(Panel(banner_text, title="[bold]TEKNOFEST 2026[/bold]", border_style="blue"))


def parse_args() -> argparse.Namespace:
    """Komut satırı argümanlarını ayrıştırır."""
    parser = argparse.ArgumentParser(
        description="Kamu Evrak Akıllı Agent Destek Sistemi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="İşlenecek evrak dosya yolu (PDF, PNG, JPG, TXT)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Çıktı dizini (varsayılan: ./output/)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["full", "classify", "draft"],
        default="full",
        help="Çalışma modu: full (uçtan uca), classify (sadece sınıflandırma), draft (sadece taslak)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Demo modunda çalıştır (örnek evraklar ile)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Web arayüzünü başlat (Streamlit)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Detaylı çıktı göster",
    )
    parser.add_argument(
        "--klasor",
        type=str,
        default=None,
        help="Dizindeki tüm .txt evrakları toplu işler; sonunda özet tablo gösterir",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        metavar="DOSYA",
        help="İşlem sonuçlarını JSON dosyasına yazar (tek evrak: nesne, klasör: liste)",
    )
    parser.add_argument(
        "--html-rapor",
        type=str,
        default=None,
        metavar="DIZIN",
        help="Her evrak için HTML işlem denetim raporunu <DIZIN>/<ad>.html olarak kaydeder",
    )
    parser.add_argument(
        "--kayit",
        action="store_true",
        help="İşlemleri evrak kayıt defterine (SQLite denetim izi) işler",
    )
    return parser.parse_args()


def run_pipeline(
    input_path: str,
    mode: str = "full",
    output_dir: str | None = None,
    pipeline: EndToEndPipeline | None = None,
) -> dict:
    """
    Evrak işleme pipeline'ını çalıştırır.

    Args:
        input_path: İşlenecek evrak dosya yolu
        mode: Çalışma modu ('full', 'classify', 'draft')
        output_dir: Çıktı dizini
        pipeline: Hazır pipeline örneği (None ise yeni oluşturulur;
            mevcut çağrılar etkilenmez)

    Returns:
        İşlem sonuçlarını içeren sözlük
    """
    input_file = Path(input_path)

    if not input_file.exists():
        console.print(f"[red]❌ Hata: Evrak dosyası bulunamadı: {input_path}[/red]")
        logger.error(f"Dosya bulunamadı: {input_path}")
        sys.exit(1)

    console.print(f"\n📄 [bold]İşlenen evrak:[/bold] {input_file.name}")
    console.print(f"⚙️  [bold]Çalışma modu:[/bold] {mode}\n")

    # Pipeline oluştur (verilmediyse) ve çalıştır
    if pipeline is None:
        pipeline = EndToEndPipeline()
    sonuc = pipeline.process(str(input_file), mode=mode)

    # Sonuçları göster
    if sonuc.get("siniflandirma"):
        console.print(Panel(
            f"[bold]Evrak Türü:[/bold] {sonuc['siniflandirma']['tur']}\n"
            f"[bold]Güven Skoru:[/bold] {sonuc['siniflandirma'].get('guven', 'N/A')}",
            title="🏷️ Sınıflandırma Sonucu",
            border_style="green",
        ))

    if sonuc.get("ozet"):
        console.print(Panel(
            sonuc["ozet"],
            title="📝 Evrak Özeti",
            border_style="yellow",
        ))

    if sonuc.get("yazi_taslagi"):
        console.print(Panel(
            sonuc["yazi_taslagi"],
            title="✍️ Resmi Yazı Taslağı",
            border_style="cyan",
        ))

    if sonuc.get("yonlendirme"):
        console.print(Panel(
            f"[bold]Önerilen Birim:[/bold] {sonuc['yonlendirme']['birim']}\n"
            f"[bold]Gerekçe:[/bold] {sonuc['yonlendirme'].get('gerekce', 'N/A')}",
            title="🏢 Birim Yönlendirme",
            border_style="magenta",
        ))

    return sonuc


def klasor_isle(klasor: str, mode: str, pipeline: EndToEndPipeline) -> list[dict]:
    """
    Dizindeki tüm .txt evrakları sırayla işler.

    Bir evrağın işlenmesi hata verse bile toplu işlem sürer; hatalı evrak
    sonuç listesine hata kaydıyla eklenir (özet tabloda görünür kalır).

    Args:
        klasor: .txt evrakları içeren dizin yolu
        mode: Çalışma modu ('full', 'classify', 'draft')
        pipeline: Paylaşılan pipeline örneği

    Returns:
        Her evrak için işlem sonucu sözlüklerinin listesi
    """
    klasor_yolu = Path(klasor)
    if not klasor_yolu.is_dir():
        console.print(f"[red]❌ Hata: Klasör bulunamadı veya dizin değil: {klasor}[/red]")
        sys.exit(1)

    dosyalar = sorted(klasor_yolu.glob("*.txt"))
    if not dosyalar:
        console.print(f"[red]❌ Hata: Klasörde işlenecek .txt evrak yok: {klasor}[/red]")
        sys.exit(1)

    console.print(f"\n📂 [bold]Toplu işlem:[/bold] {klasor_yolu} ({len(dosyalar)} evrak)\n")
    sonuclar: list[dict] = []
    for i, dosya in enumerate(dosyalar, 1):
        console.print(f"[dim]({i}/{len(dosyalar)})[/dim] 📄 {dosya.name} işleniyor...")
        try:
            sonuclar.append(pipeline.process(str(dosya), mode=mode))
        except Exception as exc:  # Tek evrak hatası toplu işlemi durdurmasın
            logger.error(f"Evrak işlenemedi ({dosya.name}): {exc}")
            console.print(f"   [red]⚠️  İşlenemedi: {exc}[/red]")
            sonuclar.append({"input_file": str(dosya), "hatalar": [f"İşlem hatası: {exc}"]})
    return sonuclar


def ozet_tablosu_goster(sonuclar: list[dict]) -> None:
    """Toplu işlem sonuçlarını rich özet tablosuyla gösterir."""
    tablo = Table(title="📋 Toplu İşlem Özeti", header_style="bold cyan")
    tablo.add_column("Dosya", overflow="fold")
    tablo.add_column("Tür")
    tablo.add_column("Birim", overflow="fold")
    tablo.add_column("Öncelik")
    tablo.add_column("Süre (sn)", justify="right")

    for sonuc in sonuclar:
        dosya_adi = Path(str(sonuc.get("input_file") or "—")).name
        if sonuc.get("hatalar") and not sonuc.get("siniflandirma"):
            tablo.add_row(dosya_adi, "[red]HATA[/red]", "—", "—", "—")
            continue
        sinif = sonuc.get("siniflandirma") or {}
        yonlendirme = sonuc.get("yonlendirme") or {}
        oncelik_bilgisi = sonuc.get("onceliklendirme") or {}
        sure = sonuc.get("islem_suresi_saniye")
        tablo.add_row(
            dosya_adi,
            str(sinif.get("tur_adi") or sinif.get("tur") or "—"),
            str(yonlendirme.get("birim") or "—"),
            str(oncelik_bilgisi.get("oncelik") or "—"),
            f"{sure:.2f}" if isinstance(sure, (int, float)) else "—",
        )
    console.print()
    console.print(tablo)


def json_ciktisi_yaz(sonuclar: list[dict], hedef: str, tek_evrak: bool) -> None:
    """
    İşlem sonuçlarını JSON dosyasına yazar.

    Args:
        sonuclar: İşlem sonucu sözlükleri
        hedef: Yazılacak JSON dosya yolu
        tek_evrak: True ise tek sonuç nesne olarak, değilse liste yazılır
    """
    veri = sonuclar[0] if (tek_evrak and len(sonuclar) == 1) else sonuclar
    hedef_yolu = Path(hedef)
    try:
        if hedef_yolu.parent != Path("."):
            hedef_yolu.parent.mkdir(parents=True, exist_ok=True)
        with open(hedef_yolu, "w", encoding="utf-8") as f:
            # default=str: serileştirilemeyen nadir değerler (ör. tarih)
            # JSON çıktısını düşürmesin diye metne indirgenir.
            json.dump(veri, f, ensure_ascii=False, indent=2, default=str)
    except OSError as exc:
        console.print(f"[red]❌ Hata: JSON dosyası yazılamadı ({hedef}): {exc}[/red]")
        sys.exit(1)
    console.print(f"💾 [green]JSON çıktısı kaydedildi:[/green] {hedef_yolu}")


def html_raporlari_yaz(sonuclar: list[dict], dizin: str) -> None:
    """
    Her evrak için HTML işlem denetim raporunu <dizin>/<ad>.html kaydeder.

    Aynı ada sahip evraklar (farklı dizinlerden) çakışırsa dosya adına
    sıra numarası eklenir; hiçbir rapor sessizce ezilmez.
    """
    from src.utils.islem_raporu import uret_html_rapor

    dizin_yolu = Path(dizin)
    try:
        dizin_yolu.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        console.print(f"[red]❌ Hata: Rapor dizini oluşturulamadı ({dizin}): {exc}[/red]")
        sys.exit(1)

    kullanilan_adlar: set[str] = set()
    for sonuc in sonuclar:
        ad = Path(str(sonuc.get("input_file") or "evrak")).stem or "evrak"
        aday, sira = ad, 2
        while aday in kullanilan_adlar:
            aday = f"{ad}_{sira}"
            sira += 1
        kullanilan_adlar.add(aday)
        rapor_yolu = dizin_yolu / f"{aday}.html"
        try:
            rapor_yolu.write_text(uret_html_rapor(sonuc), encoding="utf-8")
        except OSError as exc:
            console.print(f"[red]❌ Hata: HTML rapor yazılamadı ({rapor_yolu}): {exc}[/red]")
            sys.exit(1)
    console.print(
        f"📑 [green]{len(kullanilan_adlar)} HTML işlem raporu kaydedildi:[/green] {dizin_yolu}/"
    )


def main() -> None:
    """Ana uygulama fonksiyonu."""
    print_banner()
    args = parse_args()

    if args.verbose:
        logging.getLogger("kamu_evrak_ajan").setLevel(logging.DEBUG)

    if args.web:
        console.print("\n🌐 [bold]Web arayüzü başlatılıyor...[/bold]")
        console.print("   [dim]streamlit run src/app.py[/dim]\n")
        import subprocess
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/app.py"])
        return

    if args.demo:
        console.print("\n🎬 [bold]Demo modu başlatılıyor...[/bold]\n")
        from demo.demo_scenario import run_demo
        run_demo()
        return

    if not args.input and not args.klasor:
        if args.json or args.html_rapor or args.kayit:
            console.print(
                "\n[red]❌ Hata: --json / --html-rapor / --kayit bayrakları için "
                "işlenecek evrak gerekir (--input veya --klasor belirtin).[/red]"
            )
            sys.exit(1)
        console.print(
            "\n[yellow]⚠️  Evrak dosyası belirtilmedi.[/yellow]\n"
            "Kullanım: python -m src.main --input <evrak_dosyasi>\n"
            "          python -m src.main --klasor <evrak_dizini>\n"
            "Yardım:   python -m src.main --help\n"
        )
        return

    # Tek pipeline tüm evraklar için paylaşılır; --kayit ile denetim izi açılır.
    pipeline = EndToEndPipeline(kayit_defteri_aktif=args.kayit)
    if args.kayit:
        if pipeline.kayit_defteri is not None:
            console.print("🗂️  [dim]Kayıt defteri aktif: işlemler denetim izine yazılacak.[/dim]")
        else:
            console.print(
                "[yellow]⚠️  Kayıt defteri açılamadı; işlem kayıtsız sürdürülüyor "
                "(ayrıntı için log çıktısına bakın).[/yellow]"
            )

    sonuclar: list[dict] = []
    if args.input:
        sonuclar.append(
            run_pipeline(args.input, mode=args.mode, output_dir=args.output, pipeline=pipeline)
        )
    if args.klasor:
        sonuclar.extend(klasor_isle(args.klasor, mode=args.mode, pipeline=pipeline))
        ozet_tablosu_goster(sonuclar)

    if args.json:
        # Tek evrak (--input, klasörsüz) nesne; diğer durumlar liste yazılır.
        json_ciktisi_yaz(sonuclar, args.json, tek_evrak=bool(args.input and not args.klasor))
    if args.html_rapor:
        html_raporlari_yaz(sonuclar, args.html_rapor)


if __name__ == "__main__":
    main()
