"""Anime sahne tanımlayıcı — trace.moe API kullanır."""
import requests
import base64
import time
import os
import subprocess
import tempfile
import shutil
from pathlib import Path


TRACE_MOE_API = "https://api.trace.moe/search"
REZERO_ANILIST_IDS = {
    21355: {"season": 1, "name": "Re:Zero S1"},
    97986: {"season": 2, "name": "Re:Zero S2"},
    108632: {"season": 2, "name": "Re:Zero S2 Part 2"},
    142838: {"season": 3, "name": "Re:Zero S3"},
    189046: {"season": 4, "name": "Re:Zero S4"},
}


def identify_frame(frame_path: str, retry: int = 3) -> dict:
    result = {
        "matched": False, "anime": None, "season": None,
        "episode": None, "timestamp": 0.0, "similarity": 0.0, "is_rezero": False
    }
    for attempt in range(retry):
        try:
            with open(frame_path, "rb") as f:
                response = requests.post(
                    TRACE_MOE_API,
                    files={"image": ("frame.jpg", f, "image/jpeg")},
                    timeout=15
                )
            if response.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  trace.moe rate limit, {wait}s bekleniyor...")
                time.sleep(wait)
                continue
            if response.status_code != 200:
                print(f"  trace.moe HTTP {response.status_code}: {response.text[:200]}")
                break
            data = response.json()
            results = data.get("result", [])
            if not results:
                break
            best = results[0]
            anilist_id = best.get("anilist", 0)
            result["matched"] = True
            result["anime"] = best.get("filename", "")
            result["episode"] = best.get("episode")
            result["timestamp"] = best.get("from", 0.0)
            result["similarity"] = best.get("similarity", 0.0)
            result["is_rezero"] = anilist_id in REZERO_ANILIST_IDS
            if result["is_rezero"]:
                result["season"] = REZERO_ANILIST_IDS[anilist_id]["season"]
            break
        except requests.exceptions.Timeout:
            if attempt == retry - 1:
                result["error"] = "trace.moe zaman aşımı"
            time.sleep(2)
        except Exception as e:
            if attempt == retry - 1:
                result["error"] = str(e)
            time.sleep(2)
    return result


def batch_identify_scenes(scenes: list, video_path: str, sample_rate: int = 5) -> list:
    identified = 0
    temp_dir = tempfile.mkdtemp()
    try:
        for i, scene in enumerate(scenes):
            if i % sample_rate != 0:
                scene["trace_moe"] = None
                continue
            mid_time = scene["start"] + scene["duration"] / 2
            frame_path = os.path.join(temp_dir, f"frame_{i}.jpg")
            cmd = ["ffmpeg", "-y", "-ss", str(mid_time), "-i", video_path,
                   "-vframes", "1", "-q:v", "3", "-s", "320x180", frame_path]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0 or not os.path.exists(frame_path):
                scene["trace_moe"] = None
                continue
            result = identify_frame(frame_path)
            scene["trace_moe"] = result
            if result["is_rezero"]:
                identified += 1
            time.sleep(1.2)
            os.unlink(frame_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"  trace.moe: {identified} sahne Re:Zero olarak tanındı")
    return scenes
