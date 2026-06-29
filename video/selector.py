"""Select best clips for Shorts editing with strategy support."""
from pathlib import Path


def select_clips(
    scenes: list,
    target_duration: float = 59.0,
    min_clip: float = 1.5,
    max_clip: float = 8.0,
    strategy: str = "balanced"
) -> list:
    """
    Select best scenes to fill target duration.

    strategy:
        "balanced" — mix of action + dialogue + emotional
        "action"   — prioritize high motion
        "emotional" — prioritize dialogue + emotional

    Returns list of selected scene dicts sorted chronologically.
    """
    if not scenes:
        return []

    valid = [s for s in scenes if min_clip <= s.get("duration", 0) <= max_clip]
    if not valid:
        valid = [s for s in scenes if s.get("duration", 0) >= 1.0]
    if not valid:
        return []

    if strategy == "balanced":
        action = sorted(
            [s for s in valid if s.get("scene_type") == "action"],
            key=lambda x: x.get("final_score", 0), reverse=True
        )
        dialogue = sorted(
            [s for s in valid if s.get("scene_type") == "dialogue"],
            key=lambda x: x.get("final_score", 0), reverse=True
        )
        emotional = sorted(
            [s for s in valid if s.get("scene_type") in ("emotional", "atmospheric")],
            key=lambda x: x.get("final_score", 0), reverse=True
        )

        pool = []
        a_count = max(1, int(len(action) * 0.4)) if action else 0
        d_count = max(1, int(len(dialogue) * 0.4)) if dialogue else 0
        e_count = max(1, int(len(emotional) * 0.2)) if emotional else 0

        pool.extend(action[:a_count])
        pool.extend(dialogue[:d_count])
        pool.extend(emotional[:e_count])

        used_starts = {s.get("start", id(s)) for s in pool}
        remaining = sorted(
            [s for s in valid if s.get("start", id(s)) not in used_starts],
            key=lambda x: x.get("final_score", 0), reverse=True
        )
        pool.extend(remaining)
    else:
        pool = sorted(valid, key=lambda x: x.get("final_score", 0), reverse=True)

    selected = []
    total = 0.0

    for scene in pool:
        if total >= target_duration:
            break
        dur = min(scene.get("duration", 3.0), target_duration - total)
        if dur < 1.0:
            continue
        clip = dict(scene)
        clip["actual_duration"] = round(dur, 2)
        selected.append(clip)
        total += dur

    selected.sort(key=lambda x: x.get("start", 0))
    return selected


def select_clips_from_episodes(
    episode_analyses: list,
    target_duration: float = 59.0,
    strategy: str = "balanced"
) -> list:
    """Select clips from multiple episode analyses."""
    all_scenes = []
    for analysis in episode_analyses:
        video_path = analysis.get("path", "")
        for scene in analysis.get("scenes", []):
            s = dict(scene)
            s["video_path"] = video_path
            all_scenes.append(s)

    return select_clips(all_scenes, target_duration, strategy=strategy)
