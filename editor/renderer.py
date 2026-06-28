"""FFmpeg-based final render engine."""
import subprocess
import json
import tempfile
import shutil
import os
from pathlib import Path
from typing import Optional, Union

from audio.music_selector import select_music, analyze_clips_mood
from audio.voice_ducking import apply_ducking
from rich.console import Console

console = Console()


def render_shorts(timeline: Union[dict, str], output_path: str,
                  music_path: Optional[str] = None,
                  subtitle_path: Optional[str] = None,
                  preserve_dialogue: bool = True) -> str:
    """
    Build the final Shorts video from a timeline.

    Args:
        timeline: Timeline dict or path to a timeline JSON file.
        output_path: Output video file path.
        music_path: Optional background music file path.
        subtitle_path: Optional subtitle file path (SRT/ASS).
        preserve_dialogue: Keep original character voices audible.

    Returns:
        Path to the rendered video.
    """
    if isinstance(timeline, str):
        timeline_path = Path(timeline)
        if not timeline_path.exists():
            raise FileNotFoundError(f"Timeline dosyası bulunamadı: {timeline}")
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline = json.load(f)
    elif isinstance(timeline, Path):
        if not timeline.exists():
            raise FileNotFoundError(f"Timeline dosyası bulunamadı: {timeline}")
        with open(timeline, "r", encoding="utf-8") as f:
            timeline = json.load(f)

    clips = timeline.get("clips", [])
    if not clips:
        raise ValueError("Timeline'de klip bulunamadı")

    if music_path is None:
        mood = analyze_clips_mood(clips)
        music_path = select_music(mood)
        console.print(f"[cyan]♪ Otomatik müzik seçildi ({mood}): {Path(music_path).name}[/cyan]")

    width, height = timeline.get("resolution", [1080, 1920])
    if len(timeline.get("resolution", [])) != 2:
        width, height = 1080, 1920

    output_dir = Path(output_path).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(exist_ok=True, parents=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="rezero_render_"))
    clip_paths = []

    try:
        for i, clip in enumerate(clips):
            clip_path = _render_clip(clip, i, temp_dir, width, height)
            clip_paths.append(clip_path)

        concat_path = temp_dir / "concat.txt"
        with open(concat_path, "w", encoding="utf-8") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        temp_output = temp_dir / "merged.mp4"
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-y", str(temp_output),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Klip birleştirme hatası: {e.stderr}") from e
        except FileNotFoundError as e:
            raise RuntimeError("FFmpeg yüklü değil veya PATH'de bulunamadı") from e

        current = temp_output

        if subtitle_path and Path(subtitle_path).exists():
            subtitled_output = temp_dir / "subtitled.mp4"
            sub_cmd = [
                "ffmpeg", "-i", str(current),
                "-vf", f"subtitles={_escape_path(subtitle_path)}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-y", str(subtitled_output),
            ]
            try:
                subprocess.run(sub_cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Altyazı yakma hatası: {e.stderr}") from e
            current = subtitled_output

        if music_path and Path(music_path).exists():
            mixed_output = temp_dir / "final.mp4"
            if preserve_dialogue:
                try:
                    apply_ducking(
                        str(current), music_path, str(mixed_output),
                        dialogue_volume=1.0,
                        music_volume_normal=0.6,
                        music_volume_ducked=0.15,
                    )
                except RuntimeError as e:
                    console.print(f"[yellow]⚠ Ducking başarısız, basit karışıma dönülüyor: {e}[/yellow]")
                    preserve_dialogue = False
            if not preserve_dialogue:
                audio_cmd = [
                    "ffmpeg", "-i", str(current), "-i", music_path,
                    "-filter_complex",
                    "[0:a]volume=0.3[a0];[1:a]volume=0.7[a1];"
                    "[a0][a1]amix=inputs=2:duration=first[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac",
                    "-y", str(mixed_output),
                ]
                try:
                    subprocess.run(audio_cmd, capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Ses karıştırma hatası: {e.stderr}") from e
            current = mixed_output

        shutil.move(str(current), output_path)

    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

    return output_path


def _render_clip(clip: dict, index: int, temp_dir: Path,
                 width: int, height: int) -> str:
    """
    Render a single clip with effects applied.

    Args:
        clip: Clip data dict.
        index: Clip index for temp file naming.
        temp_dir: Temporary directory for intermediate files.
        width: Output width in pixels.
        height: Output height in pixels.

    Returns:
        Path to the rendered clip file.
    """
    source = clip.get("source", "")
    if not source or not Path(source).exists():
        raise FileNotFoundError(f"Klip kaynak dosyası bulunamadı: {source}")

    start = float(clip.get("start_time", 0.0))
    duration = float(clip.get("duration", 3.0))
    if duration <= 0:
        raise ValueError(f"Geçersiz klip süresi: {duration}")

    effects = clip.get("effects", [])

    output_path = str(temp_dir / f"clip_{index:04d}.mp4")

    scale_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    filter_chains = [scale_filter]

    if "zoom" in effects:
        filter_chains.append(
            "zoompan=z='if(eq(on,1),1,zoom+0.002)':d=25*0.5"
        )

    if "vibrant_grade" in effects:
        filter_chains.append("eq=saturation=1.5:contrast=1.2:brightness=0.05")
    elif "warm_grade" in effects:
        filter_chains.append("eq=saturation=1.1:contrast=1.0:brightness=0.1")

    vf = ",".join(filter_chains)

    cmd = [
        "ffmpeg",
        "-ss", str(start),
        "-i", source,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-y", output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Klip render hatası: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError("FFmpeg yüklü değil veya PATH'de bulunamadı") from e

    return output_path


def _escape_path(path: str) -> str:
    """Escape a file path for use in FFmpeg filter expressions."""
    return path.replace("\\", "/").replace(":", "\\:")


def convert_to_vertical(input_path: str, output_path: str) -> str:
    """
    Convert a video to 9:16 vertical format.

    Args:
        input_path: Input video path.
        output_path: Output video path.

    Returns:
        Path to the converted vertical video.
    """
    if not Path(input_path).exists():
        raise FileNotFoundError(f"Giriş dosyası bulunamadı: {input_path}")

    output_dir = Path(output_path).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(exist_ok=True, parents=True)

    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-y", output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Dikey format dönüşüm hatası: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError("FFmpeg yüklü değil veya PATH'de bulunamadı") from e

    return output_path
