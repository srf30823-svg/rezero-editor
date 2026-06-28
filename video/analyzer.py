"""OpenCV-based scene analysis utilities."""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple


# Cache the face cascade to avoid reloading it for every frame.
_FACE_CASCADE = None


def _get_face_cascade() -> cv2.CascadeClassifier:
    """Return a cached Haar face cascade classifier."""
    global _FACE_CASCADE
    if _FACE_CASCADE is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
    return _FACE_CASCADE


def detect_scenes(frame_paths: List[str], threshold: float = 30.0) -> List[Dict]:
    """
    Detect scene changes between consecutive frames.

    Args:
        frame_paths: Paths to extracted frame files.
        threshold: Scene change threshold (0-100).

    Returns:
        List of scene information dicts.
    """
    if not frame_paths:
        return []

    scenes = []
    prev_frame = None

    for i, frame_path in enumerate(frame_paths):
        try:
            img = cv2.imread(str(frame_path))
        except Exception as e:
            continue
        if img is None:
            continue

        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except cv2.error:
            continue

        motion_level = 0.0
        if prev_frame is not None:
            diff = cv2.absdiff(gray, prev_frame)
            motion_level = float(np.mean(diff))

        scenes.append({
            "timestamp": i,
            "frame_path": str(frame_path),
            "motion_level": motion_level,
            "is_scene_change": motion_level > threshold,
        })

        prev_frame = gray

    return scenes


def detect_faces(frame_path: str) -> List[Tuple[int, int, int, int]]:
    """
    Detect faces in a single frame.

    Args:
        frame_path: Path to the frame file.

    Returns:
        List of face rectangles in (x, y, w, h) format.
    """
    try:
        img = cv2.imread(str(frame_path))
    except Exception as e:
        return []
    if img is None:
        return []

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except cv2.error:
        return []

    face_cascade = _get_face_cascade()
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]


def detect_action(frame_path: str) -> float:
    """
    Estimate action intensity in a single frame.

    Args:
        frame_path: Path to the frame file.

    Returns:
        Action score from 0 to 10.
    """
    try:
        img = cv2.imread(str(frame_path))
    except Exception as e:
        return 0.0
    if img is None:
        return 0.0

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
    except cv2.error:
        return 0.0

    edge_density = np.sum(edges > 0) / edges.size
    return float(min(edge_density * 20, 10.0))


def get_motion_histogram(frame_path: str) -> Dict:
    """
    Compute motion histogram data for a frame.

    Args:
        frame_path: Path to the frame file.

    Returns:
        Dict with edge density, corner count, and action intensity.
    """
    try:
        img = cv2.imread(str(frame_path))
    except Exception as e:
        return {"edge_density": 0.0, "corner_count": 0, "action_intensity": 0.0}
    if img is None:
        return {"edge_density": 0.0, "corner_count": 0, "action_intensity": 0.0}

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
    except cv2.error:
        return {"edge_density": 0.0, "corner_count": 0, "action_intensity": 0.0}

    edge_density = np.sum(edges > 0) / edges.size

    corners = cv2.goodFeaturesToTrack(
        gray, maxCorners=100, qualityLevel=0.01, minDistance=10
    )
    corner_count = len(corners) if corners is not None else 0

    return {
        "edge_density": float(edge_density),
        "corner_count": int(corner_count),
        "action_intensity": float(min(edge_density * 15 + corner_count * 0.1, 10.0)),
    }
