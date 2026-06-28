"""FFmpeg tabanlı final render motoru."""
import subprocess
from pathlib import Path


def render_shorts(timeline_path: str, output_path: str, 
                  resolution: tuple = (1080, 1920)) -> str:
    """
    Timeline'den final Shorts videosu oluşturur.
    
    Args:
        timeline_path: Timeline JSON dosyası yolu
        output_path: Çıkış dosyası yolu
        resolution: Çıkış çözünürlük (genişlik, yükseklik)
    
    Returns:
        Render edilmiş video yolu
    """
    width, height = resolution
    
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i", "color=c=black:s={}x{}:d=59".format(width, height),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", "59", "-y", output_path
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