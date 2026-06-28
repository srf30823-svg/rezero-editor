"""Video library scanner for RE:ZERO seasons and episodes."""
import re
from pathlib import Path
from typing import Dict, List, Optional

from knowledge.lore_engine import get_arc_info


_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}


def _season_dir(base_path: str, season: int) -> Path:
    """Return the path for a season directory (S01, S02, ...)."""
    return Path(base_path) / f"S{season:02d}"


def _episode_number(filename: str) -> Optional[int]:
    """Extract episode number from filenames like E01.mp4, E12.mkv, etc."""
    match = re.search(r"[Ee](\d+)", Path(filename).stem)
    if match:
        return int(match.group(1))
    return None


def scan_library(base_path: str) -> Dict[str, Dict[int, str]]:
    """
    Scan all videos under `base_path` organized as S01/E01.mp4.

    Args:
        base_path: Root input directory (e.g. /data/data/com.termux/files/home/storage/shared/Download/rezero/input).

    Returns:
        Dict mapping season keys (e.g. 'S01') to episode dicts:
        {season: {episode_number: video_path}}.
    """
    base = Path(base_path)
    if not base.exists():
        raise FileNotFoundError(f"Kütüphane dizini bulunamadı: {base_path}")

    library: Dict[str, Dict[int, str]] = {}

    for season_dir in sorted(base.iterdir()):
        if not season_dir.is_dir():
            continue
        season_match = re.match(r"S(\d+)", season_dir.name, re.IGNORECASE)
        if not season_match:
            continue

        season_key = season_dir.name.upper()
        library[season_key] = {}

        for video_file in sorted(season_dir.iterdir()):
            if not video_file.is_file():
                continue
            if video_file.suffix.lower() not in _VIDEO_EXTENSIONS:
                continue
            episode = _episode_number(video_file.name)
            if episode is None:
                continue
            library[season_key][episode] = str(video_file.resolve())

    return library


def get_season_videos(season: int, base_path: str = None) -> List[str]:
    """
    Return all video paths for a specific season.

    Args:
        season: Season number (e.g. 1 for S01).
        base_path: Root input directory. If None, read from config.yaml.

    Returns:
        Sorted list of video file paths.
    """
    if base_path is None:
        base_path = _load_input_base_from_config()

    library = scan_library(base_path)
    season_key = f"S{season:02d}"
    episodes = library.get(season_key, {})
    return [episodes[ep] for ep in sorted(episodes)]


def get_episode_path(season: int, episode: int, base_path: str = None) -> str:
    """
    Return the full path for a specific season/episode file.

    Args:
        season: Season number.
        episode: Episode number.
        base_path: Root input directory. If None, read from config.yaml.

    Returns:
        Path to the episode video file.

    Raises:
        FileNotFoundError: If the episode does not exist.
    """
    if base_path is None:
        base_path = _load_input_base_from_config()

    library = scan_library(base_path)
    season_key = f"S{season:02d}"
    episode_path = library.get(season_key, {}).get(episode)
    if not episode_path:
        raise FileNotFoundError(f"S{season:02d}/E{episode:02d}.mp4 bulunamadı")
    return episode_path


def get_music_tracks(music_dir: str = None) -> List[str]:
    """
    Return all audio files in the music directory.

    Args:
        music_dir: Music directory path. If None, read from config.yaml.

    Returns:
        Sorted list of music file paths.
    """
    if music_dir is None:
        music_dir = _load_music_dir_from_config()

    path = Path(music_dir)
    if not path.exists():
        raise FileNotFoundError(f"Müzik dizini bulunamadı: {music_dir}")

    tracks = [
        str(f.resolve())
        for f in sorted(path.iterdir())
        if f.is_file() and f.suffix.lower() in _AUDIO_EXTENSIONS
    ]
    return tracks


def season_to_arc(season: int) -> int:
    """
    Map a season number to its primary arc number.

    Args:
        season: Season number (1-5).

    Returns:
        Primary arc number used by the lore engine.
    """
    # Season 1 covers arcs 1-4 in the lore mapping (episodes 1-25).
    # Season 2 covers arc 5 (episodes 26-50).
    # Season 3+ are not yet in the lore mapping; default to arc 5.
    if season == 1:
        return 4
    if season >= 2:
        return 5
    return 1


def get_season_intensity(season: int) -> float:
    """
    Return the intensity score of the arc associated with a season.

    Args:
        season: Season number.

    Returns:
        Arc intensity score (0-10), or 0 if unknown.
    """
    arc_number = season_to_arc(season)
    arc_info = get_arc_info(arc_number)
    return float(arc_info.get("intensity", 0))


def _load_config() -> dict:
    """Load config.yaml if available."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_input_base_from_config() -> str:
    """Return input_base from config or default Android path."""
    config = _load_config()
    return config.get("paths", {}).get(
        "input_base", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input"
    )


def _load_music_dir_from_config() -> str:
    """Return music_dir from config or default Android path."""
    config = _load_config()
    return config.get("paths", {}).get(
        "music_dir", "/data/data/com.termux/files/home/storage/shared/Download/rezero/input/music"
    )
