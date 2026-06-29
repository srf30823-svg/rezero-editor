"""Scene analysis cache — analyze once, reuse forever."""
import json
import hashlib
from pathlib import Path


CACHE_DIR = Path.home() / ".rezero_cache"


def get_video_hash(video_path: str) -> str:
    """Fast hash using file size + first 1MB."""
    p = Path(video_path)
    size = p.stat().st_size
    with open(p, "rb") as f:
        head = f.read(1024 * 1024)
    return hashlib.md5(f"{size}:{head[:100]}".encode()).hexdigest()[:12]


def get_cache_path(video_path: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    h = get_video_hash(video_path)
    name = Path(video_path).stem
    return CACHE_DIR / f"{name}_{h}.json"


def load_cache(video_path: str) -> dict | None:
    """Load cached analysis if exists."""
    cp = get_cache_path(video_path)
    if cp.exists():
        try:
            with open(cp, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_cache(video_path: str, data: dict) -> None:
    """Save analysis result to cache."""
    cp = get_cache_path(video_path)
    CACHE_DIR.mkdir(exist_ok=True)
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clear_cache(video_path: str = None) -> int:
    """Clear cache for specific video or all."""
    CACHE_DIR.mkdir(exist_ok=True)
    if video_path:
        cp = get_cache_path(video_path)
        if cp.exists():
            cp.unlink()
            return 1
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count
