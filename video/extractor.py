"""FFmpeg tabanlı video çerçeve çıkarımı."""
from pathlib import Path
import subprocess


def extract_frames(video_path: str, interval: float = 1.0) -> list:
    """
    Videodan çerçeveler çıkarır.
    
    Args:
        video_path: Video dosyası yolu
        interval: Çerçeve çıkarım aralığı (saniye)
    
    Returns:
        Çıkarılan çerçeve dosyalarının yolları
    """
    output_dir = Path("/tmp/rezero_frames")
    output_dir.mkdir(exist_ok=True)
    
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{interval}",
        str(output_dir / "frame_%04d.jpg")
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)
    
    return sorted(output_dir.glob("frame_*.jpg"))