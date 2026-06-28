#!/usr/bin/env python3
"""RE:ZERO SHORTS EDITOR - CLI entry point."""
import click
import json
import yaml
import shutil
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from video.extractor import extract_frames, extract_audio, get_video_info
from video.analyzer import detect_scenes
from video.scorer import score_scenes
from video.selector import select_clips
from audio.beat_detector import detect_beats
from audio.sync_engine import sync_to_beats
from editor.effects import apply_effects
from editor.timeline import create_timeline
from editor.renderer import render_shorts
from editor.captions import generate_captions, generate_srt, generate_ass
from video.scanner import scan_library, get_music_tracks, season_to_arc
from audio.matcher import match_music_to_arc

console = Console()

CONFIG_PATH = Path("config.yaml")


def _load_config() -> dict:
    """Load config.yaml."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _handle_error(step: str, e: Exception) -> None:
    """Display an error message and exit."""
    msg = str(e).strip()
    console.print(f"[red]✗ {step} sırasında hata: {msg}[/red]")
    raise SystemExit(1)


def _check_dependency(name: str, cmd: list, install_hint: str) -> bool:
    """Check whether an external dependency is installed."""
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(f"  [red]✗ {name} bulunamadı[/red]")
        console.print(f"    Kurulum: {install_hint}")
        return False


def _parse_episode_range(range_str: str, available: dict) -> list:
    """Parse episode range string (e.g. '1-25', '1-5', '1-10,15') into sorted list."""
    if not range_str:
        return sorted(available.keys())
    episodes = set()
    for part in range_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for ep in range(int(start), int(end) + 1):
                    if ep in available:
                        episodes.add(ep)
            except ValueError:
                continue
        else:
            try:
                ep = int(part)
                if ep in available:
                    episodes.add(ep)
            except ValueError:
                continue
    return sorted(episodes)


def _generate_shorts(video_path: str, music_path: str, output_path: str,
                     target_duration: float) -> None:
    """Generate a shorts video from a single episode."""
    from video.extractor import extract_frames, extract_audio
    from video.analyzer import detect_scenes
    from video.scorer import score_scenes
    from video.selector import select_clips
    from audio.beat_detector import detect_beats
    from audio.sync_engine import sync_to_beats
    from editor.effects import apply_effects
    from editor.captions import generate_captions, generate_srt, generate_ass
    from editor.timeline import create_timeline
    from editor.renderer import render_shorts

    frames = extract_frames(video_path)
    if not frames:
        raise RuntimeError("Videodan çerçeve çıkarılamadı")

    scenes = detect_scenes(frames)
    if not scenes:
        raise RuntimeError("Hiç sahne tespit edilemedi")

    scored = score_scenes(scenes)
    clips = select_clips(scored, target_duration=target_duration)
    if not clips:
        raise RuntimeError("Hiç klip seçilemedi")

    beat_data = detect_beats(music_path)
    synced = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])
    for clip in synced:
        apply_effects(clip)
    captioned = generate_captions(synced)

    timeline = create_timeline(captioned)
    timeline_data = timeline.to_json()
    for clip_data in timeline_data["clips"]:
        clip_data["source"] = video_path

    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True, parents=True)

    output_stem = Path(output_path).stem
    srt_content = generate_srt(captioned)
    srt_path = str(output_dir / f"{output_stem}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    ass_content = generate_ass(captioned)
    ass_path = str(output_dir / f"{output_stem}.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    render_shorts(timeline_data, output_path, music_path=music_path, subtitle_path=srt_path)


def _extract_frames_safe(video_path: str) -> list:
    """Safely extract frames, returning empty list on error."""
    try:
        from video.extractor import extract_frames
        return extract_frames(video_path)
    except Exception:
        return []


@click.group()
def cli():
    """RE:ZERO Shorts Editor - Otomatik YouTube Shorts video editörü."""
    pass


@cli.command()
@click.option("--input", "-i", required=True, help="Analiz edilecek video dosyası")
@click.option("--output", "-o", default="analysis.json", help="Analiz sonucu çıkış dosyası")
@click.option("--duration", "-d", default=None, help="Hedef klip süresi (saniye)")
def analyze(input, output, duration):
    """Analyze a video file and detect/select the best scenes."""
    video_path = Path(input)
    if not video_path.exists():
        console.print(f"[red]Hata: '{input}' dosyası bulunamadı[/red]")
        raise SystemExit(1)

    config = _load_config()
    target_duration = float(duration) if duration else config.get("output", {}).get("duration_seconds", 59)

    console.print(Panel("Video analizi başlatılıyor...", title="RE:ZERO Editor"))
    console.print(f"[yellow]Video: {input}[/yellow]")
    console.print(f"[yellow]Hedef süre: {target_duration}s[/yellow]")

    try:
        frames = extract_frames(str(video_path))
        if not frames:
            raise RuntimeError("Videodan çerçeve çıkarılamadı; dosya bozuk veya desteklenmiyor olabilir")

        scenes = detect_scenes(frames)
        if not scenes:
            raise RuntimeError("Hiç sahne tespit edilemedi")

        scored_scenes = score_scenes(scenes)
        selected_clips = select_clips(scored_scenes, target_duration=target_duration)
        if not selected_clips:
            console.print("[yellow]⚠ Eşik değeri geçen sahne bulunamadı, tüm sahneler analiz edildi[/yellow]")
            selected_clips = select_clips(
                scored_scenes,
                target_duration=target_duration,
                min_duration=0.5,
            )

        result = {
            "input": str(video_path),
            "target_duration": target_duration,
            "total_frames": len(frames),
            "total_scenes": len(scenes),
            "selected_clips": len(selected_clips),
            "scenes": scored_scenes,
            "clips": selected_clips,
        }

        output_dir = Path(output).parent
        if output_dir and not output_dir.exists():
            output_dir.mkdir(exist_ok=True, parents=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✓ Analiz tamamlandı: {output}[/green]")
        console.print(f"[green]  {len(selected_clips)} klip seçildi[/green]")

    except Exception as e:
        _handle_error("Video analizi", e)


@cli.command()
@click.option("--input", "-i", required=True, help="Kaynak video dosyası")
@click.option("--music", "-m", default=None, help="Müzik dosyası (belirtilmezse otomatik seçilir)")
@click.option("--duration", "-d", default=None, help="Çıkış videosu süresi (saniye)")
@click.option("--output", "-o", default="output/shorts.mp4", help="Çıkış dosyası")
@click.option("--language", "-l", default="tr", help="Altyazı dili (tr/en)")
@click.option("--no-subs", is_flag=True, help="Altyazıları devre dışı bırak")
def edit(input, music, duration, output, language, no_subs):
    """Create a Shorts video from source video and music."""
    video_path = Path(input)

    if not video_path.exists():
        console.print(f"[red]Hata: Video '{input}' dosyası bulunamadı[/red]")
        raise SystemExit(1)

    music_path = Path(music) if music else None

    if music_path and not music_path.exists():
        console.print(f"[red]Hata: Müzik '{music}' dosyası bulunamadı[/red]")
        raise SystemExit(1)

    config = _load_config()
    target_duration = float(duration) if duration else config.get("output", {}).get("duration_seconds", 59)

    console.print(Panel("Shorts editörü başlatılıyor...", title="RE:ZERO Editor"))
    console.print(f"[yellow]Video: {input}[/yellow]")
    if music:
        console.print(f"[yellow]Müzik: {music}[/yellow]")
    else:
        console.print(f"[yellow]Müzik: Otomatik seçilecek[/yellow]")
    console.print(f"[yellow]Süre: {target_duration}s[/yellow]")
    console.print(f"[yellow]Altyazı: {'Açık' if not no_subs else 'Kapalı'} ({language})[/yellow]")

    try:
        console.print("[blue]→ Video analiz ediliyor...[/blue]")
        frames = extract_frames(str(video_path))
        if not frames:
            raise RuntimeError("Videodan çerçeve çıkarılamadı; dosya bozuk veya desteklenmiyor olabilir")

        scenes = detect_scenes(frames)
        if not scenes:
            raise RuntimeError("Hiç sahne tespit edilemedi")

        scored = score_scenes(scenes)
        clips = select_clips(scored, target_duration=target_duration)
        if not clips:
            raise RuntimeError("Hiç klip seçilemedi; eşik çok yüksek veya video çok kısa olabilir")
        console.print(f"[green]✓ {len(clips)} klip seçildi[/green]")

        if music_path:
            console.print("[blue]→ Müzik beat'leri tespit ediliyor...[/blue]")
            beat_data = detect_beats(str(music_path))
            if beat_data.get("bpm", 0) <= 0:
                console.print("[yellow]⚠ Beat tespit edilemedi, müzik sessiz veya ritimsiz olabilir[/yellow]")
            console.print(f"[green]✓ BPM: {beat_data['bpm']:.1f}[/green]")

            console.print("[blue]→ Klipler beat'lere senkronize ediliyor...[/blue]")
            synced_clips = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])
        else:
            synced_clips = clips

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

        output_dir = Path(output).parent
        if output_dir and not output_dir.exists():
            output_dir.mkdir(exist_ok=True, parents=True)

        output_stem = Path(output).stem
        timeline_path = f"{output_dir}/{output_stem}_timeline.json"
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline_data, f, indent=2, ensure_ascii=False)

        srt_path = None
        if not no_subs:
            srt_content = generate_srt(captioned_clips)
            srt_path = f"{output_dir}/{output_stem}.srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            ass_content = generate_ass(captioned_clips)
            ass_path = f"{output_dir}/{output_stem}.ass"
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

            console.print(f"[green]✓ Altyazılar oluşturuldu: {srt_path}, {ass_path}[/green]")

        console.print("[blue]→ Video render ediliyor...[/blue]")
        result = render_shorts(
            timeline_data, output,
            music_path=str(music_path) if music_path else None,
            subtitle_path=srt_path if not no_subs else None,
        )

        console.print(f"[green]✓ Shorts videosu oluşturuldu: {result}[/green]")

    except Exception as e:
        _handle_error("Shorts oluşturma", e)


@cli.command()
@click.option("--timeline", "-t", required=True, help="Edit timeline dosyası")
@click.option("--output", "-o", required=True, help="Çıkış dosyası")
@click.option("--music", "-m", default=None, help="Arka plan müzik dosyası (opsiyonel)")
@click.option("--subtitle", "-s", default=None, help="Altyazı dosyası (opsiyonel, SRT/ASS)")
def export(timeline, output, music, subtitle):
    """Render a final Shorts video from a timeline file."""
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

    try:
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline_data = json.load(f)

        result = render_shorts(
            timeline_data, output,
            music_path=music,
            subtitle_path=subtitle,
        )
        console.print(f"[green]✓ Video oluşturuldu: {result}[/green]")

    except Exception as e:
        _handle_error("Video render", e)


@cli.command()
def validate():
    """Check system dependencies and project structure."""
    console.print(Panel("Sistem kontrolü yapılıyor...", title="RE:ZERO Editor"))

    all_ok = True

    console.print("\n[bold]Harici Araçlar:[/bold]")
    if not _check_dependency("FFmpeg", ["ffmpeg", "-version"],
                             "apt install ffmpeg  veya  brew install ffmpeg"):
        all_ok = False
    if not _check_dependency("FFprobe", ["ffprobe", "-version"],
                             "FFmpeg ile birlikte gelir"):
        all_ok = False

    console.print("\n[bold]Python Paketleri:[/bold]")
    pkgs = [
        ("opencv-python-headless", "pip install opencv-python-headless"),
        ("librosa", "pip install librosa"),
        ("click", "pip install click"),
        ("pyyaml", "pip install pyyaml"),
        ("rich", "pip install rich"),
        ("numpy", "pip install numpy"),
    ]
    for name, hint in pkgs:
        try:
            __import__(name.replace("-", "_").replace(".", "_"))
            console.print(f"  [green]✓ {name}[/green]")
        except ImportError:
            console.print(f"  [red]✗ {name} bulunamadı[/red]")
            console.print(f"    Kurulum: {hint}")
            all_ok = False

    console.print("\n[bold]Proje Yapısı:[/bold]")
    required_dirs = ["video", "audio", "editor", "knowledge", "tests"]
    for d in required_dirs:
        if Path(d).is_dir():
            console.print(f"  [green]✓ {d}/[/green]")
        else:
            console.print(f"  [red]✗ {d}/ eksik[/red]")
            all_ok = False

    if all_ok:
        console.print(f"\n[green]✓ Tüm kontroller geçildi. Sistem hazır.[/green]")
    else:
        console.print(f"\n[yellow]⚠ Bazı bileşenler eksik. Yukarıdaki uyarıları kontrol edin.[/yellow]")

    return all_ok


@cli.command()
def scan():
    """Scan all seasons and list available episodes."""
    config = _load_config()
    input_base = config.get("paths", {}).get("input_base", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input")

    console.print(Panel("RE:ZERO Video Kütüphanesi:", title="Tarama"))

    try:
        library = scan_library(input_base)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Hata: {e}[/red]")
        console.print(f"    Kütüphane yolunu config.yaml'deki 'paths.input_base' ile ayarlayın")
        raise SystemExit(1)

    if not library:
        console.print("[yellow]⚠ Kütüphanede video bulunamadı[/yellow]")
        return

    music_dir = config.get("paths", {}).get("music_dir", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input/music")
    try:
        music_tracks = get_music_tracks(music_dir)
    except FileNotFoundError:
        music_tracks = []

    console.print()
    for season_key in sorted(library.keys()):
        episodes = library[season_key]
        console.print(f"{season_key}: {len(episodes)} bölüm")
        for ep in sorted(episodes.keys())[:10]:
            console.print(f"  E{ep:02d}.mp4")
        if len(episodes) > 10:
            console.print(f"  ... ve {len(episodes) - 10} daha")

    if music_tracks:
        console.print()
        console.print(f"Müzik: {len(music_tracks)} parça")
        for track in music_tracks[:5]:
            console.print(f"  {Path(track).name}")
        if len(music_tracks) > 5:
            console.print(f"  ... ve {len(music_tracks) - 5} daha")
    else:
        console.print()
        console.print("[yellow]⚠ Müzik dizininde parça bulunamadı[/yellow]")


@cli.command()
@click.option("--season", "-s", required=True, type=int, help="Sezon numarası (1-5)")
@click.option("--episodes", "-e", default=None, help="Bölüm aralığı (1-25, 1-5, veya 1-10,15)")
@click.option("--music", "-m", default=None, help="Müzik dosyası (veya arka plan için None)")
@click.option("--output-dir", "-o", default=None, help="Çıkış dizini (varsayılan: output/shorts)")
@click.option("--duration", "-d", default=None, type=int, help="Her shorts süresi (saniye)")
def batch(season, episodes, music, output_dir, duration):
    """Generate shorts from multiple episodes automatically."""
    config = _load_config()

    if not music:
        music_dir = config.get("paths", {}).get("music_dir", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input/music")
        try:
            music = match_music_to_arc(season_to_arc(season), music_dir)
            console.print(f"[green]✓ Müzik otomatik seçildi: {Path(music).name}[/green]")
        except FileNotFoundError as e:
            console.print(f"[red]✗ Müzik hatası: {e}[/red]")
            raise SystemExit(1)

    target_duration = duration or config.get("output", {}).get("duration_seconds", 59)

    output_base = Path(output_dir) if output_dir else Path(config.get("output", {}).get("directory", "output")) / "shorts"
    output_base.mkdir(parents=True, exist_ok=True)

    library = scan_library(config.get("paths", {}).get("input_base", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input"))
    season_key = f"S{season:02d}"
    episodes_dict = library.get(season_key, {})

    if not episodes_dict:
        console.print(f"[red]✗ S{season:02d} sezonunda bölüm bulunamadı[/red]")
        raise SystemExit(1)

    episode_range = _parse_episode_range(episodes, episodes_dict)
    if not episode_range:
        console.print(f"[red]✗ Geçersiz bölüm aralığı: {episodes}[/red]")
        raise SystemExit(1)

    console.print(Panel(f"Bölüm: {len(episode_range)} - Maksimum süre: {target_duration}s", title="Batch Shorts"))

    for ep in episode_range:
        episode_path = episodes_dict[ep]
        output_name = f"S{season:02d}_E{ep:02d}_shorts.mp4"
        output_path = output_base / output_name

        console.print(f"\n[blue]→ {output_name} oluşturuluyor...[/blue]")
        try:
            _generate_shorts(episode_path, music, output_path, target_duration)
            console.print(f"[green]✓ {output_name} tamamlandı[/green]")
        except Exception as e:
            console.print(f"[red]✗ {output_name} başarısız: {e}[/red]")


@cli.command()
@click.option("--season", "-s", required=True, type=int, help="Sezon numarası (1-5)")
@click.option("--music", "-m", required=True, help="Müzik dosyası")
@click.option("--duration", "-d", default=None, type=int, help="Çıkış videosu süresi (saniye)")
def best(season, music, duration):
    """Select the best scenes from all seasons for a mega shorts."""
    config = _load_config()
    target_duration = duration or config.get("output", {}).get("duration_seconds", 59)

    console.print(Panel(f"Best S{season:02d} Shorts - Maksimum süre: {target_duration}s", title="Mega Shorts"))

    library = scan_library(config.get("paths", {}).get("input_base", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input"))
    season_key = f"S{season:02d}"
    episodes_dict = library.get(season_key, {})

    if not episodes_dict:
        console.print(f"[red]✗ S{season:02d} sezonunda bölüm bulunamadı[/red]")
        raise SystemExit(1)

    console.print(f"[blue]→ {len(episodes_dict)} bölüm taranıyor...[/blue]")

    all_scenes = []
    for ep in sorted(episodes_dict.keys()):
        episode_path = episodes_dict[ep]
        console.print(f"  E{ep:02d} ... ", end="", flush=True)
        try:
            frames = _extract_frames_safe(episode_path)
            if frames:
                scenes = detect_scenes(frames)
                if scenes:
                    scored = score_scenes(scenes, season=season)
                    all_scenes.extend(scored)
                    console.print(f"[green]{len(scenes)} sahne[/green]")
                else:
                    console.print("[yellow]sahne yok[/yellow]")
            else:
                console.print("[yellow]boş[/yellow]")
        except Exception as e:
            console.print(f"[red]hata: {e}[/red]")

    if not all_scenes:
        console.print("[yellow]⚠ Hiç sahne seçilemedi[/yellow]")
        return

    console.print(f"\n[blue]→ {len(all_scenes)} sahne analiz edildi[/blue]")
    console.print(f"[blue]→ En iyi {target_duration}s için klipler seçiliyor...[/blue]")

    clips = select_clips(all_scenes, target_duration=target_duration)

    if not clips:
        console.print("[yellow]⚠ Eşik çok yüksek, daha düşük bir değer deneyin[/yellow]")
        return

    console.print(f"[green]✓ {len(clips)} klip seçildi[/green]")

    output_path = Path(config.get("paths", {}).get("output_dir", "output/shorts")) / f"S{season:02d}_best_shorts.mp4"
    console.print(f"[blue]→ Video render ediliyor...[/blue]")

    timeline = create_timeline(clips)
    timeline_data = timeline.to_json()
    for clip_data in timeline_data["clips"]:
        clip_data["source"] = str(Path(episodes_dict[sorted(episodes_dict.keys())[0]]).parent.parent)

    beat_data = detect_beats(music)
    synced_clips = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])
    for clip in synced_clips:
        apply_effects(clip)
    captioned_clips = generate_captions(synced_clips)

    output_dir = Path(output_path).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(exist_ok=True, parents=True)

    output_stem = Path(output_path).stem
    timeline_path = f"{output_dir}/{output_stem}_timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline_data, f, indent=2, ensure_ascii=False)

    srt_path = None
    srt_content = generate_srt(captioned_clips)
    srt_path = f"{output_dir}/{output_stem}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    ass_content = generate_ass(captioned_clips)
    ass_path = f"{output_dir}/{output_stem}.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    console.print(f"[green]✓ Altyazılar oluşturuldu: {srt_path}, {ass_path}[/green]")

    result = render_shorts(
        timeline_data, str(output_path),
        music_path=music,
        subtitle_path=srt_path,
    )

    console.print(f"[green]✓ Best shorts oluşturuldu: {result}[/green]")


if __name__ == "__main__":
    cli()
