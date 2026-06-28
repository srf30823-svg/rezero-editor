"""Audio mixing engine."""
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from audio.voice_ducking import apply_ducking


def mix_audio(video_path: str, music_path: str,
              music_volume: float = 0.7,
              original_volume: float = 0.3,
              fade_duration: float = 0.5) -> str:
    """
    Mix original audio with background music and apply fades.

    Args:
        video_path: Path to the video file with original audio.
        music_path: Path to the background music file.
        music_volume: Background music volume.
        original_volume: Original audio volume.
        fade_duration: Fade in/out duration in seconds.

    Returns:
        Path to the mixed audio file.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")
    if not Path(music_path).exists():
        raise FileNotFoundError(f"Müzik dosyası bulunamadı: {music_path}")

    temp_dir = Path(tempfile.mkdtemp(prefix="rezero_mix_"))
    output_path = str(temp_dir / "mixed_audio.mp3")

    filter_complex = (
        f"[0:a]volume={original_volume},afade=t=in:ss=0:d={fade_duration},"
        f"afade=t=out:st='max(0,0.5)':d={fade_duration}[a0];"
        f"[1:a]volume={music_volume}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first[a]"
    )

    cmd = [
        "ffmpeg", "-i", video_path, "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "[a]", "-b:a", "192k",
        "-y", output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        raise RuntimeError(f"Ses karıştırma hatası: {e.stderr}") from e
    except FileNotFoundError as e:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        raise RuntimeError("FFmpeg yüklü değil veya PATH'de bulunamadı") from e

    return output_path


def mix_with_ducking(video_path: str, music_path: str, output_path: str) -> str:
    """Mix video audio (dialogue) with background music using ducking."""
    return apply_ducking(video_path, music_path, output_path)
