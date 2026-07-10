"""
Demo Senaryosu — Sistemin uçtan uca çalışmasını gösterir.

Farklı evrak türleri üzerinde sistemin tüm yeteneklerini sergiler.
"""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Proje kök dizinini path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

console = Console()

# Demo evrak dosyaları
DEMO_EVRAKLAR = [
    {
        "dosya": "data/raw/kurgu_evraklar/ornek_dilekce.txt",
        "aciklama": "Bilgi İşlem altyapı sorunu hakkında dilekçe",
    },
    {
        "dosya": "data/raw/kurgu_evraklar/ornek_ust_yazi.txt",
        "aciklama": "Dijital Dönüşüm Eylem Planı üst yazısı",
    },
    {
        "dosya": "data/raw/kurgu_evraklar/ornek_tutanak.txt",
        "aciklama": "İnsan Kaynakları toplantı tutanağı",
    },
]


def run_demo() -> None:
    """Demo senaryosunu çalıştırır."""
    console.print(Panel(
        "[bold cyan]🎬 Demo Senaryosu[/bold cyan]\n\n"
        "Bu demo, farklı evrak türleri üzerinde sistemin\n"
        "uçtan uca çalışmasını göstermektedir.",
        title="TEKNOFEST 2026 — Kamu Evrak Akıllı Ajan",
        border_style="blue",
    ))

    # Demo evraklarını listele
    table = Table(title="Demo Evrakları")
    table.add_column("#", style="bold")
    table.add_column("Dosya", style="cyan")
    table.add_column("Açıklama", style="green")

    for i, evrak in enumerate(DEMO_EVRAKLAR, 1):
        dosya_path = project_root / evrak["dosya"]
        status = "✅" if dosya_path.exists() else "❌"
        table.add_row(str(i), f"{status} {evrak['dosya']}", evrak["aciklama"])

    console.print(table)
    console.print()

    # Her evrakı işle
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    pipeline = EndToEndPipeline()

    for i, evrak in enumerate(DEMO_EVRAKLAR, 1):
        dosya_path = project_root / evrak["dosya"]

        if not dosya_path.exists():
            console.print(f"[red]❌ Dosya bulunamadı: {dosya_path}[/red]")
            continue

        console.print(Panel(
            f"[bold]Evrak {i}/{len(DEMO_EVRAKLAR)}:[/bold] {evrak['aciklama']}",
            border_style="yellow",
        ))

        try:
            sonuc = pipeline.process(str(dosya_path))

            # Sonuçları göster
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

    # Özet
    if sonuc.get("ozet"):
        console.print(Panel(sonuc["ozet"], title="📝 Özet", border_style="cyan"))

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

    # İşlem süresi
    if sonuc.get("islem_suresi_saniye"):
        console.print(f"\n⏱️  İşlem süresi: {sonuc['islem_suresi_saniye']:.2f} saniye")


if __name__ == "__main__":
    run_demo()
