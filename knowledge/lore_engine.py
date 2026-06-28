"""Re:Zero lore query engine - provides character and arc information."""
import json
from pathlib import Path
from typing import Optional, Dict, List

CHARACTERS_PATH = Path(__file__).parent / "characters.json"
ARCS_PATH = Path(__file__).parent / "arcs.json"
MOMENTS_PATH = Path(__file__).parent / "moments.json"

_cache: Dict[str, dict] = {}


def _load_json(path: Path) -> dict:
    """Load a JSON file once and cache it."""
    cache_key = str(path.resolve())
    if cache_key not in _cache:
        if not path.exists():
            raise FileNotFoundError(f"Lore dosyası bulunamadı: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                _cache[cache_key] = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Lore dosyası okunamadı: {path} - {e}")
    return _cache[cache_key]


def get_character_score(name: str) -> dict:
    """
    Return scores for a specific character.

    Args:
        name: Character name to search (full name or alias).

    Returns:
        Dict with character scores and info.
    """
    data = _load_json(CHARACTERS_PATH)
    name_lower = name.lower()

    for char_key, char_data in data["characters"].items():
        if char_key.lower() == name_lower:
            return char_data
        if any(alias.lower() == name_lower for alias in char_data.get("aliases", [])):
            return char_data

    return {"error": f"Karakter '{name}' bulunamadı"}


def get_arc_info(arc_number: int) -> dict:
    """
    Return information for a specific arc.

    Args:
        arc_number: Arc number (1-6).

    Returns:
        Dict with arc information.
    """
    data = _load_json(ARCS_PATH)
    arc_key = str(arc_number)

    if arc_key not in data["arcs"]:
        return {"error": f"Arc {arc_number} bulunamadı"}

    return data["arcs"][arc_key]


def classify_scene(intensity: float, duration: float) -> str:
    """
    Determine the scene type based on intensity and duration.

    Args:
        intensity: Scene intensity (0-10 scale).
        duration: Scene duration in seconds.

    Returns:
        Scene type: action, emotional, dialogue, or atmospheric.
    """
    if intensity >= 7:
        return "action"
    elif intensity >= 4:
        return "emotional"
    elif duration > 10:
        return "dialogue"
    else:
        return "atmospheric"


def get_top_characters(n: int = 5) -> List[dict]:
    """
    Return the top characters by fan favorite score.

    Args:
        n: Number of characters to return.

    Returns:
        List of top characters.
    """
    data = _load_json(CHARACTERS_PATH)

    sorted_chars = sorted(
        data["characters"].items(),
        key=lambda x: x[1].get("fan_favorite_score", 0),
        reverse=True
    )

    return [{"key": k, **v} for k, v in sorted_chars[:n]]


def get_moments_by_arc(arc_number: int) -> List[dict]:
    """
    Return moments for a specific arc.

    Args:
        arc_number: Arc number.

    Returns:
        List of moments for that arc.
    """
    data = _load_json(MOMENTS_PATH)
    return [m for m in data.get("moments", []) if m.get("arc") == arc_number]


def get_moments_by_character(character_name: str) -> List[dict]:
    """
    Return moments featuring a specific character.

    Args:
        character_name: Character name.

    Returns:
        List of moments featuring that character.
    """
    data = _load_json(MOMENTS_PATH)
    name_lower = character_name.lower()
    return [
        m for m in data.get("moments", [])
        if any(name_lower == c.lower() for c in m.get("characters", []))
    ]
