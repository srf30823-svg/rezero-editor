"""OpenCV tabanlı sahne analizi."""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple


def detect_scenes(frame_paths: List[str], threshold: float = 30.0) -> List[Dict]:
    """
    Çerçeveler arası sahne değişikliklerini tespit eder.
    
    Args:
        frame_paths: Çerçeve dosyalarının yolları
        threshold: Sahne değişiklik eşik değeri (0-100)
    
    Returns:
        Sahne bilgileri içeren liste
    """
    scenes = []
    prev_frame = None
    
    for i, frame_path in enumerate(frame_paths):
        img = cv2.imread(str(frame_path))
        if img is None:
            continue
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        motion_level = 0.0
        
        if prev_frame is not None:
            diff = cv2.absdiff(gray, prev_frame)
            motion_level = np.mean(diff)
        
        scenes.append({
            "timestamp": i,
            "frame_path": str(frame_path),
            "motion_level": float(motion_level),
            "is_scene_change": motion_level > threshold
        })
        
        prev_frame = gray
    
    return scenes


def detect_faces(frame_path: str) -> List[Tuple[int, int, int, int]]:
    """
    Çerçevede yüz tespiti yapar.
    
    Args:
        frame_path: Çerçeve dosyası yolu
    
    Returns:
        (x, y, w, h) formatında yüz konumları listesi
    """
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    img = cv2.imread(str(frame_path))
    if img is None:
        return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    
    return [(x, y, w, h) for (x, y, w, h) in faces]


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


def get_motion_histogram(frame_path: str) -> Dict:
    """
    Çerçevenin hareket histogramını hesaplar.
    
    Args:
        frame_path: Çerçeve dosyası yolu
    
    Returns:
        Hareket analizi verileri
    """
    img = cv2.imread(str(frame_path))
    if img is None:
        return {"edge_density": 0, "corner_count": 0}
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    edge_density = np.sum(edges > 0) / edges.size
    
    corners = cv2.goodFeaturesToTrack(
        gray, maxCorners=100, qualityLevel=0.01, minDistance=10
    )
    corner_count = len(corners) if corners is not None else 0
    
    return {
        "edge_density": float(edge_density),
        "corner_count": corner_count,
        "action_intensity": min(edge_density * 15 + corner_count * 0.1, 10.0)
    }