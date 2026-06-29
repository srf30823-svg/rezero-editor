"""Deep scene analysis: FFmpeg scene detection + face + trace.moe + local DB."""
import subprocess
import json
import os
import re
from pathlib import Path
from video.cache import load_cache, save_cache
from knowledge.face_analyzer import analyze_scene_faces
from knowledge.scene_identifier import batch_identify_scenes, TRACE_MOE_QUOTA_EXCEEDED
from knowledge.rezero_lore_db import score_scene_importance
from video.local_scene_db import batch_match_local, index_video

DEFAULT_THRESHOLD = 0.12


def get_video_duration(video_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", video_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = json.loads(r.stdout)
    return float(data["format"]["duration"])


def has_audio_stream(video_path: str) -> bool:
    """Check if video has an audio stream (1 quick ffprobe call)."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    data = json.loads(r.stdout) if r.stdout else {}
    for s in data.get("streams", []):
        if s.get("codec_type") == "audio":
            return True
    return False


def detect_scene_changes(video_path: str, threshold: float = None) -> list:
    """
    Detect scene changes using FFmpeg (keyframe scan for speed).
    Anime-safe threshold default 0.12.

    Returns list of timestamps (seconds) where scenes change.
    """
    if threshold is None:
        threshold = DEFAULT_THRESHOLD

    cmd = [
        "ffmpeg",
        "-skip_frame", "nokey",
        "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "0",
        "-an",
        "-threads", "2",
        "-f", "null", "-"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    timestamps = [0.0]
    for line in (r.stderr + r.stdout).split("\n"):
        if "pts_time:" in line:
            try:
                parts = line.split("pts_time:")[1].split()
                t = float(parts[0]) if parts else 0.0
                if t - timestamps[-1] >= 1.5:
                    timestamps.append(t)
            except (ValueError, IndexError):
                pass

    return sorted(timestamps)


def estimate_scene_motion(scene_idx: int, scene_count: int) -> float:
    """Estimate motion based on scene position — faster than per-scene ffmpeg."""
    if scene_idx < scene_count * 0.3:
        return 6.0
    elif scene_idx < scene_count * 0.7:
        return 7.0
    else:
        return 8.0


def deep_analyze_video(video_path: str, use_cache: bool = True, use_trace: bool = True,
                        season: int = 0, episode: int = 0) -> dict:
    """
    Full deep analysis of a video file. Results are cached.

    1. Scene detection at 360p (fast)
    2. Single audio stream check
    3. Motion estimation from scene position
    4. Anime face detection (OpenCV lbpcascade)
    5. trace.moe scene identification + local DB fallback
    6. Local scene fingerprint indexing

    Returns:
        path, duration, scenes (start, end, duration, scene_type, intensity, ...)
    """
    if use_cache:
        cached = load_cache(video_path)
        if cached:
            return cached

    print(f"  Analiz ediliyor: {Path(video_path).name}")

    duration = get_video_duration(video_path)
    has_audio = has_audio_stream(video_path)
    scene_times = detect_scene_changes(video_path)

    if not scene_times or scene_times[-1] < duration - 2:
        scene_times.append(duration)

    scenes = []
    for i in range(len(scene_times) - 1):
        start = scene_times[i]
        end = scene_times[i + 1]
        seg_duration = end - start

        if seg_duration < 1.5:
            continue

        motion = estimate_scene_motion(i, len(scene_times))

        if motion >= 7.0:
            scene_type = "action"
            base_score = motion
        elif has_audio and motion < 4.0:
            scene_type = "dialogue"
            base_score = 6.0
        elif motion >= 4.0:
            scene_type = "emotional"
            base_score = motion * 0.8 + 2.0
        else:
            scene_type = "atmospheric"
            base_score = 4.0

        scenes.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(seg_duration, 2),
            "motion_score": round(motion, 2),
            "has_dialogue": has_audio,
            "scene_type": scene_type,
            "intensity": round(motion, 2),
            "score": round(base_score, 2),
            "final_score": round(base_score, 2),
        })

    scenes = analyze_scene_faces(scenes, video_path, sample_rate=5)

    if use_trace:
        scenes = batch_identify_scenes(scenes, video_path, sample_rate=10)
        if TRACE_MOE_QUOTA_EXCEEDED:
            scenes = batch_match_local(scenes, video_path, sample_rate=10)

    if season > 0 and episode > 0:
        index_video(video_path, season, episode, scenes, sample_rate=15)

    for s in scenes:
        tm = s.get("trace_moe")
        lore_score = score_scene_importance(s) if tm and isinstance(tm, dict) else 0
        if lore_score > 0:
            s["final_score"] = round(min(s.get("final_score", s["score"]) + lore_score, 10.0), 2)
            s["is_key_moment"] = lore_score >= 8.0

    result = {
        "path": video_path,
        "duration": duration,
        "scenes": scenes,
        "total_scenes": len(scenes)
    }

    if use_cache:
        save_cache(video_path, result)
        print(f"  ✓ {len(scenes)} sahne bulundu, cache'e kaydedildi")

    return result
