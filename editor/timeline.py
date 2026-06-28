"""Edit timeline oluşturma motoru."""
from typing import List, Dict
import json


class Timeline:
    """Edit timeline sınıfı."""
    
    def __init__(self, fps: int = 30, width: int = 1080, height: int = 1920):
        """
        Timeline'i başlatır.
        
        Args:
            fps: Kare hızı
            width: Çıkış genişliği
            height: Çıkış yüksekliği
        """
        self.fps = fps
        self.width = width
        self.height = height
        self.clips = []
    
    def add_clip(self, clip: Dict):
        """Klip ekler."""
        self.clips.append(clip)
    
    def to_json(self) -> dict:
        """Timeline'i JSON'a dönüştürür."""
        return {
            "fps": self.fps,
            "resolution": [self.width, self.height],
            "clips": self.clips
        }


def create_timeline(clips: List[Dict], output_config: Dict = None) -> Timeline:
    """
    Videoklip timeline oluşturur.
    
    Args:
        clips: Klip listesi
        output_config: Çıkış yapılandırması
    
    Returns:
        Timeline nesnesi
    """
    config = output_config or {
        "resolution": [1080, 1920],
        "fps": 30
    }
    
    timeline = Timeline(
        fps=config.get("fps", 30),
        width=config[0] if isinstance(config["resolution"], list) else config["resolution"][0],
        height=config[1] if isinstance(config["resolution"], list) else config["resolution"][1]
    )
    
    for clip in clips:
        timeline.add_clip(clip)
    
    return timeline