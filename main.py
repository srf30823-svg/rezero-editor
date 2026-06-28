#!/usr/bin/env python3
"""RE:ZERO SHORTS EDITOR - CLI entry point."""
import click
import json
import yaml
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

CONFIG_PATH = Path("config.yaml")


def _load_config() -> dict:
    """config.yaml dosyasını yükler."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


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
@click.option("--duration", "-d", default=None, help="Çıkış videosu süresi (saniye)")
@click.option("--output", "-o", default="output/shorts.mp4", help="Çıkış dosyası")
@click.option("--language", "-l", default="tr", help="Altyazı dili (tr/en)")
@click.option("--no-subs", is_flag=True, help="Altyazıları devre dışı bırak")
def edit(input, music, duration, output, language, no_subs):
    """Video ve müziği birleştirerek Shorts oluşturur."""
    video_path = Path(input)
    music_path = Path(music)

    for p, label in [(video_path, "Video"), (music_path, "Müzik")]:
        if not p.exists():
            console.print(f"[red]Hata: '{p}' dosyası bulunamadı[/red]")
            raise SystemExit(1)

    config = _load_config()
    target_duration = float(duration) if duration else config.get("output", {}).get("duration_seconds", 59)

    console.print(Panel("Shorts editörü başlatılıyor...", title="RE:ZERO Editor"))
    console.print(f"[yellow]Video: {input}[/yellow]")
    console.print(f"[yellow]Müzik: {music}[/yellow]")
    console.print(f"[yellow]Süre: {target_duration}s[/yellow]")
    console.print(f"[yellow]Altyazı: {'Açık' if not no_subs else 'Kapalı'} ({language})[/yellow]")

    from video.extractor import extract_frames
    from video.analyzer import detect_scenes
    from video.scorer import score_scenes
    from video.selector import select_clips
    from audio.beat_detector import detect_beats
    from audio.sync_engine import sync_to_beats
    from editor.effects import apply_effects
    from editor.timeline import create_timeline
    from editor.renderer import render_shorts
    from editor.captions import generate_captions, generate_srt, generate_ass

    console.print("[blue]→ Video analiz ediliyor...[/blue]")
    frames = extract_frames(str(video_path))
    scenes = detect_scenes(frames)
    scored = score_scenes(scenes)
    clips = select_clips(scored, target_duration=target_duration)
    console.print(f"[green]✓ {len(clips)} klip seçildi[/green]")

    console.print("[blue]→ Müzik beat'leri tespit ediliyor...[/blue]")
    beat_data = detect_beats(str(music_path))
    console.print(f"[green]✓ BPM: {beat_data['bpm']:.1f}[/green]")

    console.print("[blue]→ Klipler beat'lere senkronize ediliyor...[/blue]")
    synced_clips = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])

    console.print("[blue]→ Efektler uygulanıyor...[/blue]")
    for clip in synced_clips:
        apply_effects(clip)

    console.print("[blue]→ Altyazılar oluşturuluyor...[/blue]")
    captioned_clips = generate_captions(synced_clips, language=language)

    console.print("[blue]→ Timeline oluşturuluyor...[/blue]")
    timeline = create_timeline(captioned_clips)
    timeline_data = timeline.to_json()

    for clip_data in timeline_data["clips"]:
        clip_data["source"] = str(video_path)

    Path("output").mkdir(exist_ok=True)
    output_stem = Path(output).stem

    timeline_path = f"output/{output_stem}_timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline_data, f, indent=2, ensure_ascii=False)

    srt_path = None
    if not no_subs:
        srt_content = generate_srt(captioned_clips)
        srt_path = f"output/{output_stem}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        ass_content = generate_ass(captioned_clips)
        ass_path = f"output/{output_stem}.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        console.print(f"[green]✓ Altyazılar oluşturuldu: {srt_path}, {ass_path}[/green]")

    console.print("[blue]→ Video render ediliyor...[/blue]")
    result = render_shorts(
        timeline_data, output,
        music_path=str(music_path),
        subtitle_path=srt_path if not no_subs else None
    )

    console.print(f"[green]✓ Shorts videosu oluşturuldu: {result}[/green]")


@cli.command()
@click.option("--timeline", "-t", required=True, help="Edit timeline dosyası")
@click.option("--output", "-o", required=True, help="Çıkış dosyası")
@click.option("--music", "-m", default=None, help="Arka plan müzik dosyası (opsiyonel)")
@click.option("--subtitle", "-s", default=None, help="Altyazı dosyası (opsiyonel, SRT/ASS)")
def export(timeline, output, music, subtitle):
    """Timeline dosyasından final Shorts videosu oluşturur."""
    timeline_path = Path(timeline)
    if not timeline_path.exists():
        console.print(f"[red]Hata: '{timeline}' dosyası bulunamadı[/red]")
        raise SystemExit(1)

    if subtitle and not Path(subtitle).exists():
        console.print(f"[red]Hata: '{subtitle}' altyazı dosyası bulunamadı[/red]")
        raise SystemExit(1)

    console.print(Panel("Final render başlatılıyor...", title="RE:ZERO Editor"))
    console.print(f"[yellow]Timeline: {timeline}[/yellow]")
    console.print(f"[yellow]Çıkış: {output}[/yellow]")
    if music:
        console.print(f"[yellow]Müzik: {music}[/yellow]")
    if subtitle:
        console.print(f"[yellow]Altyazı: {subtitle}[/yellow]")

    from editor.renderer import render_shorts

    result = render_shorts(
        str(timeline_path), output,
        music_path=music,
        subtitle_path=subtitle
    )
    console.print(f"[green]✓ Video oluşturuldu: {result}[/green]")


if __name__ == "__main__":
    cli()