"""FFmpeg tabanlı video çerçeve çıkarımı."""
import json
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def extract_frames(video_path: str, interval: float = 1.0, output_dir: str = "/tmp/rezero_frames") -> list:
    """
    Videodan çerçeveler çıkarır.
    
    Args:
        video_path: Video dosyası yolu
        interval: Çerçeve çıkarım aralığı (saniye)
        output_dir: Çıkış klasörü
    
    Returns:
        Çıkarılan çerçeve dosyalarının yolları
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    pattern = str(output_path / "frame_%06d.jpg")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{interval}",
        "-q:v", "2",
        pattern
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg hatası: {result.stderr}")
    
    return sorted(output_path.glob("frame_*.jpg"))


def extract_audio(video_path: str, output_path: str = "/tmp/audio.wav") -> str:
    """
    Videodan ses çıkarır.
    
    Args:
        video_path: Video dosyası yolu
        output_path: Çıkış ses dosyası yolu
    
    Returns:
        Çıkarılan ses dosyası yolu
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
        output_path, "-y"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Ses çıkarım hatası: {result.stderr}")
    
    return output_path


def get_video_info(video_path: str) -> dict:
    """
    Video meta verilerini alır.
    
    Args:
        video_path: Video dosyası yolu
    
    Returns:
        Video süresi, fps, çözünürlük gibi bilgiler içeren dict
    """
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Video bilgi hatası: {result.stderr}")
    
    data = json.loads(result.stdout)
    video_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    
    return {
        "duration": float(data["format"].get("duration", 0)),
        "fps": eval(video_stream.get("r_frame_rate", "30/1")),
        "width": video_stream.get("width", 1920),
        "height": video_stream.get("height", 1080),
        "total_frames": int(video_stream.get("nb_frames", 0))
    }


def extract_clip(video_path: str, start_time: float, end_time: float, 
                output_path: str) -> str:
    """
    Videodan bir klip kesip çıkarır.
    
    Args:
        video_path: Video dosyası yolu
        start_time: Başlangıç zamanı (saniye)
        end_time: Bitiş zamanı (saniye)
        output_path: Çıkış dosyası yolu
    
    Returns:
        Çıkarılan klip yolu
    """
    duration = end_time - start_time
    cmd = [
        "ffmpeg", "-i", video_path,
        "-ss", str(start_time), "-t", str(duration),
        "-c:v", "libx264", "-c:a", "aac",
        output_path, "-y"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Klip çıkarım hatası: {result.stderr}")
    
    return output_path