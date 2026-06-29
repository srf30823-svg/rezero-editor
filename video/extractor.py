"""FFmpeg-based video frame extraction and clip utilities."""
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def _run_ffmpeg(cmd: List[str]) -> str:
    """Run FFmpeg and return stdout, raising on errors."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg hatası: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError("FFmpeg yüklü değil veya PATH'de bulunamadı") from e
    return result.stdout


def extract_frames(video_path: str, interval: float = 1.0,
                   output_dir: str = "/tmp/rezero_frames") -> List[str]:
    """
    Extract frames from a video file.

    Args:
        video_path: Path to the video file.
        interval: Frame extraction interval in seconds.
        output_dir: Output directory for extracted frames.

    Returns:
        List of extracted frame file paths.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

    output_path = Path(output_dir)
    if output_path.exists():
        shutil.rmtree(str(output_path), ignore_errors=True)
    output_path.mkdir(exist_ok=True, parents=True)

    pattern = str(output_path / "frame_%06d.jpg")
    cmd = [
        "ffmpeg",
        "-ss", "0",
        "-i", video_path,
        "-vf", f"fps=1/{interval}",
        "-q:v", "2",
        "-y",
        pattern,
    ]

    _run_ffmpeg(cmd)

    return [str(p) for p in sorted(output_path.glob("frame_*.jpg"))]


def extract_audio(video_path: str, output_path: str = "/tmp/audio.wav") -> str:
    """
    Extract audio from a video file.

    Args:
        video_path: Path to the video file.
        output_path: Output audio file path.

    Returns:
        Path to the extracted audio file.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True, parents=True)

    cmd = [
        "ffmpeg",
        "-ss", "0",
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
        "-y", output_path,
    ]

    _run_ffmpeg(cmd)

    return output_path


def get_video_info(video_path: str) -> Dict:
    """
    Retrieve video metadata.

    Args:
        video_path: Path to the video file.

    Returns:
        Dict with duration, fps, width, height, and total frames.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", video_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video bilgi hatası: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError("FFprobe yüklü değil veya PATH'de bulunamadı") from e

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"FFprobe çıktısı okunamadı: {e}") from e

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        {}
    )
    if not video_stream:
        raise RuntimeError("Videoda görüntü akışı bulunamadı (corrupted veya ses dosyası?)")

    r_frame_rate = video_stream.get("r_frame_rate", "30/1")
    try:
        num, den = map(int, r_frame_rate.split("/"))
        fps = num / den if den != 0 else 30.0
    except (ValueError, ZeroDivisionError):
        fps = 30.0

    return {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "fps": fps,
        "width": video_stream.get("width", 1920),
        "height": video_stream.get("height", 1080),
        "total_frames": int(video_stream.get("nb_frames", 0)),
    }


def extract_clip(
    video_path: str,
    start_time: float,
    end_time: float,
    output_path: str,
    target_duration: float = None
) -> str:
    """
    Extract a clip with original audio preserved and vertical format.

    Uses fast seek (-ss before -i) and scales to 1080x1920 9:16.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

    if start_time < 0 or end_time <= start_time:
        raise ValueError(f"Geçersiz klip zaman aralığı: {start_time}-{end_time}")

    duration = target_duration or (end_time - start_time)
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True, parents=True)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        output_path
    ]

    _run_ffmpeg(cmd)

    return output_path
