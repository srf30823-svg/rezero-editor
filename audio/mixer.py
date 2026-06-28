"""Ses karıştırma motoru."""
import subprocess
from pathlib import Path


def mix_audio(video_path: str, music_path: str, 
             music_volume: float = 0.7, 
             original_volume: float = 0.3,
             fade_duration: float = 0.5) -> str:
    """
    Orijinal ses ile müziği karıştırır.
    
    Args:
        video_path: Video dosyası yolu
        music_path: Müzik dosyası yolu
        music_volume: Müzik ses seviyesi
        original_volume: Orijinal ses seviyesi
        fade_duration: Fade süresi (saniye)
    
    Returns:
        Karıştırılmış ses dosyası yolu
    """
    output_path = "/tmp/mixed_audio.mp3"
    
    cmd = [
        "ffmpeg", "-i", video_path, "-i", music_path,
        "-filter_complex",
        f"[0:a]volume={original_volume}[a0];"
        f"[1:a]volume={music_volume}[a1];"
        f"[a0][a1]amix=inputs=2[a]",
        "-map", "a", "-b:a", "192k",
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)
    
    return output_path