"""Yerel sahne veritabanı — perceptual hash ile frame eşleştirme, trace.moe alternatifi."""
import json
import os
import subprocess
import struct
import tempfile
import shutil
import sqlite3
from pathlib import Path

DB_PATH = os.path.expanduser("~/.rezero_cache/scene_fingerprints.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER,
            episode INTEGER,
            timestamp REAL,
            dhash INTEGER,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dhash ON fingerprints(dhash)
    """)
    conn.commit()
    return conn


def _dhash_from_video(video_path: str, timestamp: float, size: str = "9x8") -> int:
    """Extract difference hash from a video frame."""
    try:
        r = subprocess.run([
            "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
            "-vf", f"scale={size}:flags=bilinear",
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
        return h & 0x7FFFFFFFFFFFFFFF  # SQLite INTEGER safe (63-bit)
    except Exception:
        return 0


def _hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def index_video(video_path: str, season: int, episode: int,
                scenes: list, sample_rate: int = 15) -> int:
    """Index all scene frames from a video into the local DB."""
    conn = _get_db()
    indexed = 0
    temp_dir = tempfile.mkdtemp()
    try:
        for i, scene in enumerate(scenes):
            if i % sample_rate != 0:
                continue
            mid = scene["start"] + scene["duration"] / 2
            fp = os.path.join(temp_dir, f"idx_{i}.jpg")
            cmd = ["ffmpeg", "-y", "-ss", str(mid), "-i", video_path,
                   "-vframes", "1", "-q:v", "2", "-s", "160x90", fp]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0 or not os.path.exists(fp):
                continue
            dhash = _dhash_from_video(video_path, mid)
            if dhash == 0:
                continue
            conn.execute(
                "INSERT INTO fingerprints (season, episode, timestamp, dhash, file_path) VALUES (?,?,?,?,?)",
                (season, episode, round(mid, 2), dhash, video_path)
            )
            indexed += 1
            os.unlink(fp)
        conn.commit()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"  Yerel DB: {indexed} frame indekslendi")
    return indexed


def match_scene(dhash: int, threshold: int = 10) -> dict:
    """Find best matching scene from local DB by dhash."""
    conn = _get_db()
    best = {"matched": False, "season": None, "episode": None,
            "timestamp": 0.0, "similarity": 0.0}

    rows = conn.execute(
        "SELECT season, episode, timestamp, dhash FROM fingerprints"
    ).fetchall()

    for season, episode, ts, stored_hash in rows:
        stored_hash = stored_hash & 0x7FFFFFFFFFFFFFFF
        dist = _hamming_distance(dhash, stored_hash)
        if dist == 0:
            best.update({"matched": True, "season": season, "episode": episode,
                         "timestamp": ts, "similarity": 1.0})
            return best
        if dist <= threshold:
            sim = 1.0 - (dist / 64.0)
            if sim > best["similarity"]:
                best.update({"matched": True, "season": season, "episode": episode,
                             "timestamp": ts, "similarity": round(sim, 4)})

    return best


def batch_match_local(scenes: list, video_path: str, sample_rate: int = 10) -> list:
    """Match scenes against local DB using dhash."""
    matched = 0
    temp_dir = tempfile.mkdtemp()
    try:
        for i, scene in enumerate(scenes):
            if i % sample_rate != 0:
                continue
            mid = scene["start"] + scene["duration"] / 2
            fp = os.path.join(temp_dir, f"m_{i}.jpg")
            cmd = ["ffmpeg", "-y", "-ss", str(mid), "-i", video_path,
                   "-vframes", "1", "-q:v", "2", "-s", "160x90", fp]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0 or not os.path.exists(fp):
                continue
            dhash = _dhash_from_video(video_path, mid)
            if dhash == 0:
                continue
            match = match_scene(dhash)
            if match["matched"]:
                scene["trace_moe"] = {
                    "matched": True, "is_rezero": True,
                    "season": match["season"],
                    "episode": match["episode"],
                    "timestamp": match["timestamp"],
                    "similarity": match["similarity"],
                    "source": "local_db",
                }
                matched += 1
            os.unlink(fp)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    if matched:
        print(f"  Yerel DB: {matched} sahne eşleşti")
    return scenes


def stats() -> dict:
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0]
    episodes = conn.execute("SELECT COUNT(DISTINCT episode||'.'||season) FROM fingerprints").fetchone()[0]
    return {"total_frames": count, "total_episodes": episodes}


def clear():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        return True
    return False
