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

from video.scanner import scan_library, get_music_tracks, season_to_arc
from video.deep_analyzer import deep_analyze_video

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
                     target_duration: float, use_llm: bool = True) -> None:
    """Generate a shorts video from a single episode using deep analysis."""
    from video.selector import select_clips
    from editor.effects import apply_effects
    from editor.timeline import create_timeline
    from editor.renderer import render_shorts
    from editor.captions import generate_captions, generate_srt, generate_ass

    console.print("[blue]→ Derin video analizi basliyor...[/blue]")
    analysis = deep_analyze_video(video_path)
    scene_count = analysis.get("total_scenes", 0)
    console.print(f"[green]✓ {scene_count} sahne tespit edildi[/green]")

    clips = select_clips(
        analysis.get("scenes", []),
        target_duration=target_duration,
    )
    if not clips:
        raise RuntimeError("Hiç klip seçilemedi")

    for c in clips:
        c["source"] = video_path
        c["start_time"] = c.get("start", 0.0)
        c["duration"] = c.get("actual_duration", c.get("duration", 3.0))

    console.print(f"[green]✓ {len(clips)} klip seçildi[/green]")

    if music_path:
        try:
            from audio.beat_detector import detect_beats
            from audio.sync_engine import sync_to_beats
            console.print("[blue]→ Müzik beat'leri tespit ediliyor...[/blue]")
            beat_data = detect_beats(music_path)
            if beat_data.get("bpm", 0) > 0:
                console.print(f"[green]✓ BPM: {beat_data['bpm']:.1f}[/green]")
                clips = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])
            else:
                console.print("[yellow]⚠ Beat tespit edilemedi, senkronizasyon atlandi[/yellow]")
        except ImportError:
            console.print("[yellow]⚠ librosa paketi eksik, beat senkronizasyonu atlandi[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠ Beat tespiti basarisiz: {e}, senkronizasyon atlandi[/yellow]")

    console.print("[blue]→ Efektler uygulaniyor...[/blue]")
    for clip in clips:
        apply_effects(clip)

    captioned = generate_captions(clips)

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

    console.print("[blue]→ Video render ediliyor...[/blue]")
    render_shorts(
        timeline_data, output_path,
        music_path=music_path,
        subtitle_path=srt_path,
        use_llm=use_llm,
    )


def _extract_frames_safe(video_path: str) -> list:
    """Safely extract frames, returning empty list on error."""
    try:
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
@click.option("--no-trace", is_flag=True, help="trace.moe analizini devre dışı bırak")
def analyze(input, output, duration, no_trace):
    """Deep-analyze a video and cache the results."""
    video_path = Path(input)
    if not video_path.exists():
        console.print(f"[red]Hata: '{input}' dosyası bulunamadı[/red]")
        raise SystemExit(1)

    config = _load_config()
    target_duration = float(duration) if duration else config.get("output", {}).get("duration_seconds", 59)

    console.print(Panel("Derin video analizi başlatılıyor...", title="RE:ZERO Editor"))
    console.print(f"[yellow]Video: {input}[/yellow]")

    try:
        analysis = deep_analyze_video(str(video_path), use_trace=not no_trace)

        from video.selector import select_clips
        clips = select_clips(
            analysis.get("scenes", []),
            target_duration=target_duration,
        )

        result = {
            "input": str(video_path),
            "target_duration": target_duration,
            "duration": analysis.get("duration", 0),
            "total_scenes": analysis.get("total_scenes", 0),
            "selected_clips": len(clips),
            "scenes": analysis.get("scenes", []),
            "clips": clips,
        }

        output_path = Path(output)
        output_dir = output_path.parent
        if output_dir and not output_dir.exists():
            output_dir.mkdir(exist_ok=True, parents=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✓ Analiz tamamlandı: {output}[/green]")
        console.print(f"[green]  {len(clips)} klip seçildi[/green]")

    except Exception as e:
        _handle_error("Video analizi", e)


@cli.command()
@click.option("--input", "-i", required=True, help="Kaynak video dosyası")
@click.option("--music", "-m", default=None, help="Müzik dosyası (belirtilmezse otomatik seçilir)")
@click.option("--duration", "-d", default=None, help="Çıkış videosu süresi (saniye)")
@click.option("--output", "-o", default="output/shorts.mp4", help="Çıkış dosyası")
@click.option("--language", "-l", default="tr", help="Altyazı dili (tr/en)")
@click.option("--no-subs", is_flag=True, help="Altyazıları devre dışı bırak")
@click.option("--no-llm", is_flag=True, help="Kural tabanlı mod (hızlı, ücretsiz, LLM yok)")
@click.option("--no-trace", is_flag=True, help="trace.moe analizini devre dışı bırak (hızlı mod)")
@click.option("--threads", default=2, type=int, help="FFmpeg thread sayısı (CPU render hızı)")
@click.option("--no-hwaccel", is_flag=True, help="Donanım ivmesini devre dışı bırak")
def edit(input, music, duration, output, language, no_subs, no_llm, no_trace, threads, no_hwaccel):
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

    if no_llm:
        console.print("[yellow]⚡ Kural tabanlı mod (LLM devre dışı)[/yellow]")
    else:
        console.print("[cyan]🦉 Owl Alpha Director: Aktif[/cyan]")

    try:
        analysis = deep_analyze_video(str(video_path), use_trace=not no_trace)
        scene_count = analysis.get("total_scenes", 0)
        console.print(f"[green]✓ {scene_count} sahne tespit edildi[/green]")

        from video.selector import select_clips
        clips = select_clips(
            analysis.get("scenes", []),
            target_duration=target_duration,
        )
        if not clips:
            raise RuntimeError("Hiç klip seçilemedi")

        for c in clips:
            c["source"] = str(video_path)
            c["start_time"] = c.get("start", 0.0)
            c["duration"] = c.get("actual_duration", c.get("duration", 3.0))

        console.print(f"[green]✓ {len(clips)} klip seçildi[/green]")

        if music_path:
            try:
                from audio.beat_detector import detect_beats
                from audio.sync_engine import sync_to_beats
                console.print("[blue]→ Müzik beat'leri tespit ediliyor...[/blue]")
                beat_data = detect_beats(str(music_path))
                if beat_data.get("bpm", 0) > 0:
                    console.print(f"[green]✓ BPM: {beat_data['bpm']:.1f}[/green]")
                    clips = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])
                else:
                    console.print("[yellow]⚠ Beat tespit edilemedi, senkronizasyon atlandi[/yellow]")
            except ImportError:
                console.print("[yellow]⚠ librosa paketi eksik, beat senkronizasyonu atlandi[/yellow]")
            except Exception as e:
                console.print(f"[yellow]⚠ Beat tespiti basarisiz: {e}, senkronizasyon atlandi[/yellow]")

        from editor.effects import apply_effects
        console.print("[blue]→ Efektler uygulaniyor...[/blue]")
        for clip in clips:
            apply_effects(clip)

        from editor.captions import generate_captions, generate_srt, generate_ass
        console.print("[blue]→ Altyazılar oluşturuluyor...[/blue]")
        captioned_clips = generate_captions(clips, language=language, minimal=True)

        from editor.timeline import create_timeline
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

        from editor.renderer import render_shorts
        console.print(f"[blue]→ Video render ediliyor... (threads={threads}, hwaccel={not no_hwaccel})[/blue]")
        result = render_shorts(
            timeline_data, output,
            music_path=str(music_path) if music_path else None,
            subtitle_path=srt_path if not no_subs else None,
            use_llm=not no_llm,
            threads=threads,
            hwaccel=not no_hwaccel,
        )

        console.print(f"[green]✓ Shorts videosu oluşturuldu: {result}[/green]")

    except Exception as e:
        _handle_error("Shorts oluşturma", e)


@cli.command()
@click.option("--timeline", "-t", required=True, help="Edit timeline dosyası")
@click.option("--output", "-o", required=True, help="Çıkış dosyası")
@click.option("--music", "-m", default=None, help="Arka plan müzik dosyası (opsiyonel)")
@click.option("--subtitle", "-s", default=None, help="Altyazı dosyası (opsiyonel, SRT/ASS)")
@click.option("--no-llm", is_flag=True, help="Kural tabanlı mod")
def export(timeline, output, music, subtitle, no_llm):
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

    if not no_llm:
        console.print("[cyan]🦉 Owl Alpha Director: Aktif[/cyan]")

    try:
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline_data = json.load(f)

        from editor.renderer import render_shorts
        result = render_shorts(
            timeline_data, output,
            music_path=music,
            subtitle_path=subtitle,
            use_llm=not no_llm,
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
        ("opencv-python-headless", "cv2", "pip install opencv-python-headless"),
        ("librosa", "librosa", "pip install librosa"),
        ("click", "click", "pip install click"),
        ("pyyaml", "yaml", "pip install pyyaml"),
        ("rich", "rich", "pip install rich"),
        ("numpy", "numpy", "pip install numpy"),
        ("openai", "openai", "pip install openai"),
        ("requests", "requests", "pip install requests"),
    ]
    for name, import_name, hint in pkgs:
        try:
            __import__(import_name)
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
    """Re:Zero video kütüphanesini tarar."""
    config = _load_config()
    input_base = config.get("paths", {}).get(
        "input_base",
        "/data/data/com.termux/files/home/storage/shared/Download/rezero/input"
    )

    base = Path(input_base)
    if not base.exists():
        console.print(f"[red]Klasör bulunamadı: {base}[/red]")
        return

    console.print(Panel("Re:Zero Video Kütüphanesi", title="SCAN"))

    total = 0
    for season_dir in sorted(base.iterdir()):
        if not season_dir.is_dir() or not season_dir.name.startswith("S"):
            continue
        episodes = sorted(season_dir.glob("*.mp4"))
        if episodes:
            console.print(f"[cyan]{season_dir.name}[/cyan]: {len(episodes)} bölüm")
            for ep in episodes:
                size = ep.stat().st_size / (1024 * 1024)
                console.print(f"  {ep.name} ({size:.1f} MB)")
            total += len(episodes)

    music_dir = Path(config.get("paths", {}).get(
        "music_dir",
        "/data/data/com.termux/files/home/storage/shared/Download/rezero/input/music"
    ))
    music_files = list(music_dir.rglob("*.mp3")) if music_dir.exists() else []
    console.print(f"\n[green]Toplam: {total} bölüm, {len(music_files)} müzik[/green]")


@cli.command()
@click.option("--season", "-s", required=True, type=int, help="Sezon numarası (1-5)")
@click.option("--episodes", "-e", default=None, help="Bölüm aralığı (1-25, 1-5, veya 1-10,15)")
@click.option("--music", "-m", default=None, help="Müzik dosyası (belirtilmezse otomatik seçilir)")
@click.option("--output-dir", "-o", default=None, help="Çıkış dizini (varsayılan: output/shorts)")
@click.option("--duration", "-d", default=None, type=int, help="Her shorts süresi (saniye)")
@click.option("--no-llm", is_flag=True, help="Kural tabanlı mod")
def batch(season, episodes, music, output_dir, duration, no_llm):
    """Generate shorts from multiple episodes automatically."""
    config = _load_config()

    if not music:
        from audio.matcher import match_music_to_arc
        music_dir = config.get("paths", {}).get(
            "music_dir",
            "/data/data/com.termux/files/home/storage/shared/Download/rezero/input/music"
        )
        try:
            music = match_music_to_arc(season_to_arc(season), music_dir)
            console.print(f"[green]✓ Müzik otomatik seçildi: {Path(music).name}[/green]")
        except FileNotFoundError as e:
            console.print(f"[red]✗ Müzik hatası: {e}[/red]")
            raise SystemExit(1)

    target_duration = duration or config.get("output", {}).get("duration_seconds", 59)

    output_base = Path(output_dir) if output_dir else Path(config.get("output", {}).get("directory", "output")) / "shorts"
    output_base.mkdir(parents=True, exist_ok=True)

    library = scan_library(config.get("paths", {}).get(
        "input_base",
        "/data/data/com.termux/files/home/storage/shared/Download/rezero/input"
    ))
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
            _generate_shorts(episode_path, music, str(output_path), target_duration, use_llm=not no_llm)
            console.print(f"[green]✓ {output_name} tamamlandı[/green]")
        except Exception as e:
            console.print(f"[red]✗ {output_name} başarısız: {e}[/red]")


@cli.command()
@click.option("--season", "-s", required=True, type=int, help="Sezon numarası (1-5)")
@click.option("--music", "-m", required=True, help="Müzik dosyası")
@click.option("--duration", "-d", default=None, type=int, help="Çıkış videosu süresi (saniye)")
@click.option("--no-llm", is_flag=True, help="Kural tabanlı mod")
def best(season, music, duration, no_llm):
    """Select the best scenes from all seasons for a mega shorts."""
    config = _load_config()
    target_duration = duration or config.get("output", {}).get("duration_seconds", 59)

    console.print(Panel(f"Best S{season:02d} Shorts - Maksimum süre: {target_duration}s", title="Mega Shorts"))

    library = scan_library(config.get("paths", {}).get(
        "input_base",
        "/data/data/com.termux/files/home/storage/shared/Download/rezero/input"
    ))
    season_key = f"S{season:02d}"
    episodes_dict = library.get(season_key, {})

    if not episodes_dict:
        console.print(f"[red]✗ S{season:02d} sezonunda bölüm bulunamadı[/red]")
        raise SystemExit(1)

    console.print(f"[blue]→ {len(episodes_dict)} bölüm taranıyor...[/blue]")

    all_analyses = []
    for ep in sorted(episodes_dict.keys()):
        episode_path = episodes_dict[ep]
        console.print(f"  E{ep:02d} ... ", end="", flush=True)
        try:
            analysis = deep_analyze_video(episode_path)
            scenes = analysis.get("scenes", [])
            if scenes:
                all_analyses.append(analysis)
                console.print(f"[green]{len(scenes)} sahne[/green]")
            else:
                console.print("[yellow]sahne yok[/yellow]")
        except Exception as e:
            console.print(f"[red]hata: {e}[/red]")

    if not all_analyses:
        console.print("[yellow]⚠ Hiç sahne seçilemedi[/yellow]")
        return

    from video.selector import select_clips_from_episodes
    clips = select_clips_from_episodes(all_analyses, target_duration=target_duration)

    if not clips:
        console.print("[yellow]⚠ Hiç klip seçilemedi[/yellow]")
        return

    console.print(f"[green]✓ {len(clips)} klip seçildi[/green]")

    for c in clips:
        c["start_time"] = c.get("start", 0.0)
        c["duration"] = c.get("actual_duration", c.get("duration", 3.0))

    try:
        from audio.beat_detector import detect_beats
        from audio.sync_engine import sync_to_beats
        beat_data = detect_beats(music)
        if beat_data.get("bpm", 0) > 0:
            clips = sync_to_beats(clips, beat_data["beat_times"], beat_data["drop_times"])
    except ImportError:
        console.print("[yellow]⚠ librosa paketi eksik, beat senkronizasyonu atlandi[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠ Beat tespiti basarisiz: {e}, senkronizasyon atlandi[/yellow]")

    from editor.effects import apply_effects
    for clip in clips:
        apply_effects(clip)

    from editor.captions import generate_captions, generate_srt, generate_ass
    captioned_clips = generate_captions(clips)

    from editor.timeline import create_timeline
    timeline = create_timeline(captioned_clips)
    timeline_data = timeline.to_json()

    output_path = Path(config.get("paths", {}).get(
        "output_dir",
        "/data/data/com.termux/files/home/storage/shared/Download/rezero/output/shorts"
    )) / f"S{season:02d}_best_shorts.mp4"
    output_dir = output_path.parent
    output_dir.mkdir(exist_ok=True, parents=True)

    output_stem = output_path.stem
    timeline_path = str(output_dir / f"{output_stem}_timeline.json")
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline_data, f, indent=2, ensure_ascii=False)

    srt_content = generate_srt(captioned_clips)
    srt_path = str(output_dir / f"{output_stem}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    ass_content = generate_ass(captioned_clips)
    ass_path = str(output_dir / f"{output_stem}.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    console.print(f"[green]✓ Altyazılar oluşturuldu[/green]")

    from editor.renderer import render_shorts
    result = render_shorts(
        timeline_data, str(output_path),
        music_path=music,
        subtitle_path=srt_path,
        use_llm=not no_llm,
    )
    console.print(f"[green]✓ Best shorts oluşturuldu: {result}[/green]")


@cli.command()
@click.option("--clear", is_flag=True, help="Tüm cache'i temizle")
@click.option("--video", "-i", default=None, help="Belirli bir video için cache temizle")
@click.option("--info", is_flag=True, help="Cache durumunu göster")
def cache(clear, video, info):
    """Yönet video analiz cache'ini."""
    from video.cache import clear_cache, CACHE_DIR

    if clear:
        count = clear_cache(video)
        if video:
            console.print(f"[green]✓ Cache temizlendi: {Path(video).name}[/green]")
        else:
            console.print(f"[green]✓ {count} cache dosyası temizlendi[/green]")
    elif info:
        CACHE_DIR.mkdir(exist_ok=True)
        files = list(CACHE_DIR.glob("*.json"))
        total_bytes = sum(f.stat().st_size for f in files)
        console.print(f"[cyan]Cache: {len(files)} dosya, {total_bytes / 1024:.1f} KB[/cyan]")
        for f in files:
            console.print(f"  {f.name}")
    else:
        console.print("[yellow]Kullanım: --clear (tümünü temizle) | --info (durum) | --clear --video video.mp4[/yellow]")


if __name__ == "__main__":
    cli()
