"""Automatic music-to-arc matching engine."""
import re
from pathlib import Path
from typing import List, Optional

from knowledge.lore_engine import get_arc_info
from video.scanner import get_music_tracks


# Map common music filename tokens to arc mood keywords.
_MOOD_TOKENS = {
    "epic": ["epic", "battle", "war", "heroic", "glory", "legend"],
    "emotional": ["emotional", "sad", "tear", "cry", "feels", "love", "heart"],
    "dark": ["dark", "horror", "fear", "creepy", "shadow", "nightmare"],
    "suspense": ["suspense", "tension", "mystery", "thriller", "anxiety"],
    "dramatic": ["dramatic", "intense", "climax", "confrontation"],
    "contemplative": ["contemplative", "calm", "soft", "peaceful", "gentle"],
    "adventure": ["adventure", "journey", "travel", "wonder", "explore"],
    "tragic": ["tragic", "despair", "death", "loss", "grief"],
    "otherworldly": ["otherworldly", "cosmic", "ethereal", "celestial"],
}


def _arc_mood_keywords(arc_number: int) -> List[str]:
    """
    Build a list of mood keywords for an arc from the lore engine.

    Args:
        arc_number: Arc number (1-6).

    Returns:
        List of lowercase mood keywords.
    """
    arc_info = get_arc_info(arc_number)
    if "error" in arc_info:
        return []

    mood = arc_info.get("recommended_music_mood", "")
    tone = arc_info.get("tone", "")

    keywords = set()
    for text in (mood, tone):
        for token in re.split(r"[+\s,./_-]", text.lower()):
            if token:
                keywords.add(token)

    # Expand using known mood tokens.
    for keyword in list(keywords):
        for mood_name, tokens in _MOOD_TOKENS.items():
            if keyword in tokens or mood_name == keyword:
                keywords.add(mood_name)
                keywords.update(tokens)

    return list(keywords)


def _score_track(track_path: str, keywords: List[str]) -> int:
    """
    Score a music file by how well its filename matches the mood keywords.

    Args:
        track_path: Path to the music file.
        keywords: List of lowercase mood keywords.

    Returns:
        Match score (higher is better).
    """
    filename = Path(track_path).stem.lower()
    filename_tokens = set(re.split(r"[\s_.-]+", filename))

    score = 0
    keyword_set = set(keywords)
    for token in filename_tokens:
        if token in keyword_set:
            score += 2
        for mood_name, tokens in _MOOD_TOKENS.items():
            if token in tokens and mood_name in keyword_set:
                score += 1

    return score


def match_music_to_arc(arc_number: int, music_dir: str) -> str:
    """
    Select the best music track for an arc's emotional tone.

    Args:
        arc_number: Arc number (1-6).
        music_dir: Directory containing music files.

    Returns:
        Path to the most suitable music file.

    Raises:
        FileNotFoundError: If no music files are found.
    """
    tracks = get_music_tracks(music_dir)
    if not tracks:
        raise FileNotFoundError(f"Müzik dizininde parça bulunamadı: {music_dir}")

    keywords = _arc_mood_keywords(arc_number)
    if not keywords:
        return tracks[0]

    scored = [(track, _score_track(track, keywords)) for track in tracks]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[0][0]


def match_music_to_season(season: int, music_dir: str) -> str:
    """
    Select the best music track for a season using its primary arc.

    Args:
        season: Season number (1-5).
        music_dir: Directory containing music files.

    Returns:
        Path to the most suitable music file.
    """
    from video.scanner import season_to_arc

    arc_number = season_to_arc(season)
    return match_music_to_arc(arc_number, music_dir)


def suggest_music(arc_number: int, music_dir: str, top_n: int = 3) -> List[str]:
    """
    Return the top N music tracks for an arc.

    Args:
        arc_number: Arc number (1-6).
        music_dir: Directory containing music files.
        top_n: Number of tracks to return.

    Returns:
        List of top matching music file paths.
    """
    tracks = get_music_tracks(music_dir)
    if not tracks:
        return []

    keywords = _arc_mood_keywords(arc_number)
    if not keywords:
        return tracks[:top_n]

    scored = [(track, _score_track(track, keywords)) for track in tracks]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [track for track, _ in scored[:top_n]]
