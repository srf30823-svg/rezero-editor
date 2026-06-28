"""FFmpeg tabanlı final render motoru."""
import subprocess
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional


def render_shorts(timeline, output_path: str,
                  music_path: Optional[str] = None,
                  subtitle_path: Optional[str] = None) -> str:
    """
    Timeline'den final Shorts videosu oluşturur.

    Args:
        timeline: Timeline verisi (dict veya JSON dosyası yolu)
        output_path: Çıkış dosyası yolu
        music_path: Arka plan müzik dosyası (opsiyonel)
        subtitle_path: Altyazı dosyası yolu (opsiyonel, SRT/ASS)

    Returns:
        Render edilmiş video yolu
    """
    if isinstance(timeline, str):
        with open(timeline, "r", encoding="utf-8") as f:
            timeline = json.load(f)

    clips = timeline.get("clips", [])
    if not clips:
        raise ValueError("Timeline'de klip bulunamadı")

    width, height = timeline.get("resolution", [1080, 1920])

    temp_dir = Path(tempfile.mkdtemp(prefix="rezero_render_"))
    clip_paths = []

    try:
        for i, clip in enumerate(clips):
            clip_path = _render_clip(clip, i, temp_dir, width, height)
            clip_paths.append(clip_path)

        concat_path = temp_dir / "concat.txt"
        with open(concat_path, "w") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        temp_output = temp_dir / "merged.mp4"
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(temp_output), "-y"
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        current = temp_output

        if subtitle_path:
            subtitled_output = temp_dir / "subtitled.mp4"
            sub_cmd = [
                "ffmpeg", "-i", str(current),
                "-vf", f"subtitles={subtitle_path}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                str(subtitled_output), "-y"
            ]
            subprocess.run(sub_cmd, capture_output=True, check=True)
            current = subtitled_output

        if music_path:
            mixed_output = temp_dir / "final.mp4"
            audio_cmd = [
                "ffmpeg", "-i", str(current), "-i", music_path,
                "-filter_complex",
                "[0:a]volume=0.3[a0];[1:a]volume=0.7[a1];"
                "[a0][a1]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac",
                str(mixed_output), "-y"
            ]
            subprocess.run(audio_cmd, capture_output=True, check=True)
            current = mixed_output

        shutil.move(str(current), output_path)

    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

    return output_path


def _render_clip(clip: dict, index: int, temp_dir: Path,
                 width: int, height: int) -> str:
    """
    Tek bir klibi efektlerle render eder.

    Args:
        clip: Klip verisi
        index: Klip sırası
        temp_dir: Geçici klasör
        width: Çıkış genişliği
        height: Çıkış yüksekliği

    Returns:
        Render edilmiş klip yolu
    """
    source = clip.get("source", "")
    start = clip.get("start_time", 0)
    duration = clip.get("duration", 3)
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
        "ffmpeg", "-i", source,
        "-ss", str(start), "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an",
        output_path, "-y"
    ]

    subprocess.run(cmd, capture_output=True, check=True)

    return output_path


def convert_to_vertical(input_path: str, output_path: str) -> str:
    """
    Videoyu 9:16 dikey formatına çevirir.

    Args:
        input_path: Giriş video yolu
        output_path: Çıkış video yolu

    Returns:
        Dikey formattaki video yolu
    """
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_path
    ]

    subprocess.run(cmd, capture_output=True, check=True)

    return output_path
