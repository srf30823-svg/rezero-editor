"""Anime yüz tespiti — lbpcascade_animeface + OpenCV."""
import cv2
import os
import subprocess
import tempfile
import shutil
import urllib.request
from pathlib import Path


CASCADE_URL = "https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml"
CASCADE_PATH = os.path.expanduser("~/.rezero_cache/lbpcascade_animeface.xml")
CACHE_DIR = os.path.dirname(CASCADE_PATH)


def _ensure_cascade():
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not os.path.exists(CASCADE_PATH):
        print("  lbpcascade_animeface indiriliyor...")
        urllib.request.urlretrieve(CASCADE_URL, CASCADE_PATH)
        print("  ✓ lbpcascade_animeface.xml kaydedildi")


def detect_faces(frame_path: str) -> list:
    _ensure_cascade()
    cascade = cv2.CascadeClassifier(CASCADE_PATH)
    img = cv2.imread(frame_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    # Equalize histogram for better detection on dark anime scenes
    gray = cv2.equalizeHist(gray)
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.05, minNeighbors=3, minSize=(20, 20)
    )
    return [{"x": int(x), "y": int(y), "w": int(w_), "h": int(h_)} for (x, y, w_, h_) in faces]


def analyze_scene_faces(scenes: list, video_path: str, sample_rate: int = 5) -> list:
    face_count = 0
    face_scenes = 0
    temp_dir = tempfile.mkdtemp()
    try:
        for i, scene in enumerate(scenes):
            if i % sample_rate != 0:
                if "has_faces" not in scene:
                    scene["has_faces"] = False
                    scene["face_count"] = 0
                    scene["faces"] = []
                continue
            mid_time = scene["start"] + scene["duration"] / 2
            frame_path = os.path.join(temp_dir, f"face_{i}.jpg")
            # Bigger frame for better detection
            cmd = ["ffmpeg", "-y", "-ss", str(mid_time), "-i", video_path,
                   "-vframes", "1", "-q:v", "2", "-s", "640x480", frame_path]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0 or not os.path.exists(frame_path):
                scene["has_faces"] = False
                scene["face_count"] = 0
                scene["faces"] = []
                continue
            faces = detect_faces(frame_path)
            scene["faces"] = faces
            if len(faces) > 0:
                face_count += len(faces)
                face_scenes += 1
                scene["has_faces"] = True
                scene["face_count"] = len(faces)
            else:
                scene["has_faces"] = False
                scene["face_count"] = 0
            os.unlink(frame_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"  Yüz tespiti: {face_count} yüz, {face_scenes} sahnede")
    return scenes
