"""Automatic music selection based on scene emotional tone."""
import os
import random
from pathlib import Path
import yaml


MOOD_MAP = {
    "action": ["action", "epic"],
    "emotional": ["emotional", "calm"],
    "dark": ["dark", "action"],
    "epic": ["epic", "action"],
    "atmospheric": ["calm", "dark"],
    "dialogue": ["calm", "emotional"],
}

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".webm"}


def get_music_dir() -> Path:
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return Path(config["paths"]["music_dir"])


def select_music(dominant_mood: str, used_tracks: list = None) -> str:
    """
    Selects the best music track for the given scene mood.

    Args:
        dominant_mood: Scene mood (action/emotional/dark/epic/atmospheric/dialogue)
        used_tracks: List of already used track paths to avoid repetition

    Returns:
        Absolute path to selected audio file
    """
    if used_tracks is None:
        used_tracks = []

    music_dir = get_music_dir()
    preferred_moods = MOOD_MAP.get(dominant_mood, ["action"])

    candidates = []
    for mood in preferred_moods:
        mood_dir = music_dir / mood
        if mood_dir.exists():
            for f in mood_dir.iterdir():
                if f.suffix.lower() in AUDIO_EXTENSIONS and str(f) not in used_tracks:
                    candidates.append(str(f))

    if not candidates:
        for f in music_dir.rglob("*"):
            if f.suffix.lower() in AUDIO_EXTENSIONS and str(f) not in used_tracks:
                candidates.append(str(f))

    if not candidates:
        raise FileNotFoundError(
            f"Müzik bulunamadı: {music_dir}\n"
            f"Lütfen {music_dir}/action/ klasörüne MP3 dosyaları ekleyin."
        )

    return random.choice(candidates)


def analyze_clips_mood(clips: list) -> str:
    """
    Analyzes a list of clips and returns the dominant mood.

    Args:
        clips: List of clip dicts with scene_type and intensity fields

    Returns:
        Dominant mood string
    """
    if not clips:
        return "action"

    mood_scores = {
        "action": 0,
        "emotional": 0,
        "dark": 0,
        "epic": 0,
        "atmospheric": 0,
        "dialogue": 0,
    }

    for clip in clips:
        scene_type = clip.get("scene_type", "action")
        intensity = clip.get("intensity", 5)
        weight = intensity / 10.0

        if scene_type in mood_scores:
            mood_scores[scene_type] += weight
        elif intensity >= 8:
            mood_scores["action"] += weight
        elif intensity >= 5:
            mood_scores["epic"] += weight
        else:
            mood_scores["emotional"] += weight

    return max(mood_scores, key=mood_scores.get)
