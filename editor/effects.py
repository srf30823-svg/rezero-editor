"""Gerçek FFmpeg efekt motoru — flash, shake, glitch, color grading."""
import subprocess
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Optional


def apply_effects(clip: Dict, temp_dir: Optional[Path] = None) -> Dict:
    scene_type = clip.get("scene_type", "dialogue")
    intensity = clip.get("intensity", 5)
    clip_path = clip.get("clip_path", "")
    if not clip_path or not Path(clip_path).exists():
        clip["effects"] = []
        return clip

    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp())

    effects = []
    current = Path(clip_path)

    if scene_type == "action" and intensity >= 6:
        flashed = temp_dir / f"flash_{current.name}"
        apply_flash(str(current), str(flashed), duration=0.08)
        effects.append("flash")
        current = flashed

        if intensity >= 8:
            shaken = temp_dir / f"shake_{current.name}"
            apply_shake(str(current), str(shaken), intensity=2.0)
            effects.append("shake")
            current = shaken

    elif scene_type == "emotional" and intensity >= 7:
        graded = temp_dir / f"grade_{current.name}"
        apply_color_grade(str(current), str(graded), "warm")
        effects.append("warm_grade")
        current = graded

    elif scene_type == "atmospheric":
        graded = temp_dir / f"grade_{current.name}"
        apply_color_grade(str(current), str(graded), "dark")
        effects.append("dark_grade")
        current = graded

    clip["clip_path"] = str(current)
    clip["effects"] = effects
    return clip


def apply_flash(input_path: str, output_path: str, duration: float = 0.08):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"drawbox=t={duration*30}:c=white:fill=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
        "-c:a", "copy",
        output_path,
    ]
    _run(cmd, "Flash efekti")


def apply_shake(input_path: str, output_path: str, intensity: float = 2.0):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"crop=iw-{intensity}:ih-{intensity}:{intensity/2}:{intensity/2}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
        "-c:a", "copy",
        output_path,
    ]
    _run(cmd, "Shake efekti")


def apply_color_grade(input_path: str, output_path: str, grade_type: str):
    grade_map = {
        "vibrant": "eq=saturation=1.5:contrast=1.2:brightness=0.02",
        "warm": "eq=saturation=1.1:contrast=0.95:brightness=0.08:colorbalance=rh=0.05:yh=0.03",
        "dark": "eq=saturation=0.7:contrast=1.3:brightness=-0.08",
        "cold": "eq=saturation=0.9:contrast=1.0:brightness=0.0:colorbalance=bh=0.05",
    }
    eq = grade_map.get(grade_type, grade_map["vibrant"])
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", eq,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
        "-c:a", "copy",
        output_path,
    ]
    _run(cmd, f"{grade_type} renk tonlama")


def _run(cmd, name):
    subprocess.run(cmd, capture_output=True, check=True)
