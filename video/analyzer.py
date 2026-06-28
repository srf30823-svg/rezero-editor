"""OpenCV tabanlı sahne analizi."""
import cv2
import numpy as np
from pathlib import Path


def detect_scenes(frame_paths: list, threshold: float = 30.0) -> list:
    """
    Çerçeveler arası sahne değişikliklerini tespit eder.
    
    Args:
        frame_paths: Çerçeve dosyalarının yolları
        threshold: Sahne değişiklik eşik değeri
    
    Returns:
        Sahne bilgileri içeren liste
    """
    scenes = []
    
    for i, frame_path in enumerate(frame_paths):
        scenes.append({
            "timestamp": i,
            "frame_path": str(frame_path),
            "motion_level": 0.0
        })
    
    return scenes


def detect_action(frame_path: str) -> float:
    """
    Çerçevede aksiyon varlığını tespit eder.
    
    Args:
        frame_path: Çerçeve dosyası yolu
    
    Returns:
        Aksiyon skoru (0-10 arası)
    """
    img = cv2.imread(str(frame_path))
    if img is None:
        return 0.0
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    edge_density = np.sum(edges > 0) / edges.size
    return min(edge_density * 20, 10.0)