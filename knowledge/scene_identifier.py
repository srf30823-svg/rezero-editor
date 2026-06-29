"""Anime sahne tanımlayıcı — trace.moe API + yerel DHash fallback."""
import requests
import time
import os
import subprocess
import tempfile
import shutil
import struct
from pathlib import Path


TRACE_MOE_API = "https://api.trace.moe/search"
REZERO_ANILIST_IDS = {
    21355: {"season": 1, "name": "Re:Zero S1"},
    97986: {"season": 2, "name": "Re:Zero S2"},
    108632: {"season": 2, "name": "Re:Zero S2 Part 2"},
    142838: {"season": 3, "name": "Re:Zero S3"},
    189046: {"season": 4, "name": "Re:Zero S4"},
}
TRACE_MOE_QUOTA_EXCEEDED = False


def _dhash(frame_path: str) -> int:
    """Perceptual hash (difference hash) for local frame matching."""
    try:
        r = subprocess.run([
            "ffmpeg", "-y", "-i", frame_path,
            "-vf", "scale=9:8:flags=bilinear",
            "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"
        ], capture_output=True, timeout=10)
        if r.returncode != 0 or len(r.stdout) < 72:
            return 0
        pixels = list(struct.unpack("B" * 72, r.stdout[:72]))
        h = 0
        for y in range(8):
            for x in range(8):
                if pixels[y * 9 + x] < pixels[y * 9 + x + 1]:
                    h |= 1 << (y * 8 + x)
        return h
    except Exception:
        return 0


def identify_frame(frame_path: str, retry: int = 2) -> dict:
    """trace.moe ile kare tanımla. Kota aşılırsa yerel hash kullan."""
    global TRACE_MOE_QUOTA_EXCEEDED

    result = {
        "matched": False, "anime": None, "season": None,
        "episode": None, "timestamp": 0.0, "similarity": 0.0, "is_rezero": False,
        "dhash": _dhash(frame_path),
    }

    if TRACE_MOE_QUOTA_EXCEEDED:
        return result

    for attempt in range(retry):
        try:
            with open(frame_path, "rb") as f:
                response = requests.post(
                    TRACE_MOE_API,
                    files={"image": ("frame.jpg", f, "image/jpeg")},
                    timeout=10
                )
            if response.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if response.status_code == 402:
                print("  ⚠ trace.moe kotası doldu ({}/24h). Yerel hash moduna geçiliyor.".format(
                    response.json().get("used", "?")))
                TRACE_MOE_QUOTA_EXCEEDED = True
                return result
            if response.status_code != 200:
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
                result["error"] = "zaman aşımı"
            time.sleep(1)
        except Exception as e:
            if attempt == retry - 1:
                result["error"] = str(e)
            time.sleep(1)
    return result


def batch_identify_scenes(scenes: list, video_path: str, sample_rate: int = 10) -> list:
    identified = 0
    temp_dir = tempfile.mkdtemp()
    try:
        for i, scene in enumerate(scenes):
            if i % sample_rate != 0:
                continue
            mid_time = scene["start"] + scene["duration"] / 2
            frame_path = os.path.join(temp_dir, f"frame_{i}.jpg")
            cmd = ["ffmpeg", "-y", "-ss", str(mid_time), "-i", video_path,
                   "-vframes", "1", "-q:v", "3", "-s", "320x180", frame_path]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0 or not os.path.exists(frame_path):
                continue
            result = identify_frame(frame_path)
            if result["is_rezero"]:
                identified += 1
            time.sleep(1.2)
            os.unlink(frame_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"  trace.moe: {identified} sahne Re:Zero olarak tanındı")
    return scenes
