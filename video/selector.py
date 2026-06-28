"""Clip selection engine that picks the best scenes for a target duration."""
from typing import List, Dict


def select_clips(scenes: List[Dict],
                 min_duration: float = 1.5,
                 max_duration: float = 8.0,
                 target_duration: float = 59.0) -> List[Dict]:
    """
    Select the best clips to reach the target duration.

    Args:
        scenes: Scored scene list.
        min_duration: Minimum clip duration in seconds.
        max_duration: Maximum clip duration in seconds.
        target_duration: Target total duration in seconds.

    Returns:
        List of selected clips.
    """
    if not scenes:
        return []

    if target_duration <= 0:
        raise ValueError("Hedef süre 0'dan büyük olmalıdır")

    # Sort by content value descending, then pick clips greedily.
    sorted_scenes = sorted(
        scenes,
        key=lambda x: x.get("content_value", 0.0),
        reverse=True,
    )

    selected = []
    total_time = 0.0

    for scene in sorted_scenes:
        intensity = scene.get("intensity", 5.0)
        duration = min(max_duration, max(min_duration, intensity / 2))

        if total_time + duration <= target_duration:
            selected.append({
                **scene,
                "duration": duration,
            })
            total_time += duration

        if total_time >= target_duration:
            break

    # Sort selected clips back to chronological order for a coherent timeline.
    selected.sort(key=lambda x: x.get("timestamp", 0))

    return selected
