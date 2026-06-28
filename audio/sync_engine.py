"""Beat-synchronized clip alignment engine."""
from typing import List, Dict


def sync_to_beats(clips: List[Dict], beat_times: List[float],
                  drop_times: List[float]) -> List[Dict]:
    """
    Align clip start times to the nearest detected beat.

    Args:
        clips: Selected clip list.
        beat_times: Detected beat times in seconds.
        drop_times: Detected drop times in seconds.

    Returns:
        List of synchronized clips.
    """
    if not clips:
        return []

    if not beat_times:
        return clips

    synced = []
    for clip in clips:
        timestamp = float(clip.get("timestamp", 0))
        start_time = find_nearest_beat(timestamp, beat_times)

        synced.append({
            **clip,
            "start_time": start_time,
            "sync_type": _sync_type(start_time, beat_times, drop_times),
        })

    return synced


def find_nearest_beat(timestamp: float, beat_times: List[float]) -> float:
    """
    Find the nearest beat time to a given timestamp.

    Args:
        timestamp: Desired time in seconds.
        beat_times: List of beat times in seconds.

    Returns:
        Nearest beat time, or the original timestamp if no beats are available.
    """
    if not beat_times:
        return timestamp

    return float(min(beat_times, key=lambda b: abs(b - timestamp)))


def _sync_type(start_time: float, beat_times: List[float],
               drop_times: List[float], tolerance: float = 0.05) -> str:
    """Classify the synchronization type for a start time."""
    for drop in drop_times:
        if abs(drop - start_time) < tolerance:
            return "drop"

    for beat in beat_times:
        if abs(beat - start_time) < tolerance:
            return "beat"

    return "nearest"
