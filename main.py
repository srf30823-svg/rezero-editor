#!/usr/bin/env python3
"""RE:ZERO SHORTS EDITOR - CLI entry point."""
import click
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group()
def cli():
    """RE:ZERO Shorts Editor - Otomatik YouTube Shorts video editörü."""
    pass


@cli.command()
@click.option("--input", "-i", required=True, help="Analiz edilecek video dosyası")
@click.option("--output", "-o", default="analysis.json", help="Analiz sonucu çıkış dosyası")
def analyze(input, output):
    """Video dosyasını analiz eder ve sahneleri tespit eder."""
    video_path = Path(input)
    if not video_path.exists():
        console.print(f"[red]Hata: '{input}' dosyası bulunamadı[/red]")
        raise SystemExit(1)
    
    console.print(Panel("Video analizi başlatılıyor...", title="RE:ZERO Editor"))
    console.print(f"[yellow]Video: {input}[/yellow]")
    
    from video.extractor import extract_frames
    from video.analyzer import detect_scenes
    from video.scorer import score_scenes
    
    frames = extract_frames(str(video_path))
    scenes = detect_scenes(frames)
    scored_scenes = score_scenes(scenes)
    
    result = {
        "input": str(video_path),
        "scenes": scored_scenes
    }
    
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    console.print(f"[green]✓ Analiz tamamlandı: {output}[/green]")


@cli.command()
@click.option("--input", "-i", required=True, help="Kaynak video dosyası")
@click.option("--music", "-m", required=True, help="Arka plan müzik dosyası")
@click.option("--duration", "-d", default=59, help="Çıkış videosu süresi (saniye)")
def edit(input, music, duration):
    """Video ve müziği birleştirerek Shorts oluşturur."""
    video_path = Path(input)
    music_path = Path(music)
    
    for p, label in [(video_path, "Video"), (music_path, "Müzik")]:
        if not p.exists():
            console.print(f"[red]Hata: '{p}' dosyası bulunamadı[/red]")
            raise SystemExit(1)
    
    console.print(Panel("Shorts editörü başlatılıyor...", title="RE:ZERO Editor"))
    
    # Workflow placeholder - will be implemented in Module 2
    console.print(f"[yellow]Video: {input}[/yellow]")
    console.print(f"[yellow]Müzik: {music}[/yellow]")
    console.print(f"[yellow]Süre: {duration}s[/yellow]")


@cli.command()
@click.option("--timeline", "-t", required=True, help="Edit timeline dosyası")
@click.option("--output", "-o", required=True, help="Çıkış dosyası")
def export(timeline, output):
    """Timeline dosyasından final Shorts videosu oluşturur."""
    timeline_path = Path(timeline)
    if not timeline_path.exists():
        console.print(f"[red]Hata: '{timeline}' dosyası bulunamadı[/red]")
        raise SystemExit(1)
    
    console.print(Panel("Final render başlatılıyor...", title="RE:ZERO Editor"))
    
    # Workflow placeholder
    console.print(f"[yellow]Timeline: {timeline}[/yellow]")
    console.print(f"[yellow]Çıkış: {output}[/yellow]")


if __name__ == "__main__":
    cli()