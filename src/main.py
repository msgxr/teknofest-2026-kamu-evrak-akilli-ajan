"""
Ana uygulama giriş noktası.

Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi'ni
başlatır ve uçtan uca evrak işleme pipeline'ını çalıştırır.
"""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.logging import RichHandler

from src.config import settings
from src.pipelines.end_to_end_pipeline import EndToEndPipeline

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
    return parser.parse_args()


def run_pipeline(input_path: str, mode: str = "full", output_dir: str | None = None) -> dict:
    """
    Evrak işleme pipeline'ını çalıştırır.

    Args:
        input_path: İşlenecek evrak dosya yolu
        mode: Çalışma modu ('full', 'classify', 'draft')
        output_dir: Çıktı dizini

    Returns:
        İşlem sonuçlarını içeren sözlük
    """
    input_file = Path(input_path)

    if not input_file.exists():
        logger.error(f"Dosya bulunamadı: {input_path}")
        sys.exit(1)

    console.print(f"\n📄 [bold]İşlenen evrak:[/bold] {input_file.name}")
    console.print(f"⚙️  [bold]Çalışma modu:[/bold] {mode}\n")

    # Pipeline oluştur ve çalıştır
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

    if args.input:
        run_pipeline(args.input, mode=args.mode, output_dir=args.output)
    else:
        console.print(
            "\n[yellow]⚠️  Evrak dosyası belirtilmedi.[/yellow]\n"
            "Kullanım: python -m src.main --input <evrak_dosyasi>\n"
            "Yardım:   python -m src.main --help\n"
        )


if __name__ == "__main__":
    main()
