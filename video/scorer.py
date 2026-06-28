"""Scene scoring engine."""
from typing import List, Dict, Optional
from knowledge.lore_engine import classify_scene, get_arc_info


# Fan-favorite scores for known characters, loaded once per process.
_CHARACTER_SCORES = {
    "rem": 2.0,
    "subaru": 1.5,
    "emilia": 1.2,
    "beatrice": 1.0,
    "echidna": 2.5,
    "elsa": 1.5,
    "satella": 2.0,
    "reinhard": 1.0,
    "ram": 0.8,
    "garfiel": 0.8,
}


def score_scenes(scenes: List[Dict], boost_multiplier: float = 1.4,
                 config: Dict = None, season: Optional[int] = None,
                 arc_number: Optional[int] = None) -> List[Dict]:
    """
    Score analyzed scenes based on intensity, character bonuses, and lore.

    Args:
        scenes: Analyzed scene list.
        boost_multiplier: Multiplier for action scenes.
        config: Configuration dict with action_boost_multiplier.
        season: Season number (1-5). If provided, arc intensity is added.
        arc_number: Direct arc number (1-6). Overrides season if provided.

    Returns:
        List of scored scenes.
    """
    if not scenes:
        return []

    config = config or {"action_boost_multiplier": 1.4}
    multiplier = config.get("action_boost_multiplier", boost_multiplier)

    arc_intensity = 0.0
    if arc_number is not None:
        arc_info = get_arc_info(arc_number)
        arc_intensity = float(arc_info.get("intensity", 0))
    elif season is not None:
        from video.scanner import season_to_arc
        arc_info = get_arc_info(season_to_arc(season))
        arc_intensity = float(arc_info.get("intensity", 0))

    scored = []
    for scene in scenes:
        motion = scene.get("motion_level", 0.0)
        intensity = motion / 10
        scene_type = classify_scene(motion, 5.0)

        if scene_type == "action":
            intensity = min(intensity * multiplier, 10.0)

        # Add arc intensity with 0.3 weight so later seasons (e.g. Sanctuary) score higher.
        if arc_intensity > 0:
            intensity = min(intensity + arc_intensity * 0.3, 10.0)

        scored.append({
            **scene,
            "intensity": round(intensity, 2),
            "scene_type": scene_type,
            "content_value": determine_content_value({**scene, "intensity": intensity}),
            "emotion_score": calculate_emotion_score({**scene, "intensity": intensity}),
            "arc_intensity_bonus": round(arc_intensity * 0.3, 2) if arc_intensity else 0.0,
        })

    return scored


def determine_content_value(scene: Dict) -> float:
    """
    Determine the content value of a scene.

    Args:
        scene: Scene data.

    Returns:
        Content value score (0-10).
    """
    base_score = scene.get("intensity", 0.0)
    scene_type = scene.get("scene_type", "dialogue")

    if scene_type == "action":
        base_score += 1.0
    elif scene_type == "emotional":
        base_score += 0.8

    return float(min(base_score, 10.0))


def calculate_emotion_score(scene: Dict) -> float:
    """
    Calculate an emotion score for a scene.

    Args:
        scene: Scene data.

    Returns:
        Emotion score (0-10).
    """
    intensity = scene.get("intensity", 0.0)
    scene_type = scene.get("scene_type", "dialogue")

    emotion_map = {
        "action": 7.0,
        "emotional": 9.0,
        "dialogue": 5.0,
        "atmospheric": 4.0,
    }

    base = emotion_map.get(scene_type, 5.0)
    return float(min(base + intensity * 0.5, 10.0))


def score_character_scene(frame_path: str, characters: List[str] = None) -> float:
    """
    Calculate a score based on detected characters in the frame path.

    Args:
        frame_path: Frame file path.
        characters: List of character names to check.

    Returns:
        Total character score.
    """
    characters = characters or list(_CHARACTER_SCORES.keys())
    frame_lower = frame_path.lower()

    total_score = 0.0
    for char in characters:
        if char.lower() in frame_lower:
            total_score += _CHARACTER_SCORES.get(char.lower(), 0.0)

    return float(total_score)
