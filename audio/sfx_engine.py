"""Anime ses efekt motoru — sahne tipine göre ses filtreleri."""
import subprocess
import shutil
from pathlib import Path


SFX_PRESETS = {
    "death": {
        "music_volume": 0.0,
        "dialogue_volume": 1.5,
        "filter": "aecho=0.8:0.88:60:0.4",
        "description": "Ölüm anı — sessizlik + echo",
    },
    "emotional": {
        "music_volume": 0.08,
        "dialogue_volume": 1.3,
        "filter": "lowpass=f=3000,aecho=0.6:0.6:40:0.3",
        "description": "Duygusal an — müzik kısık + ılık echo",
    },
    "action": {
        "music_volume": 0.6,
        "dialogue_volume": 1.0,
        "filter": "bass=g=8,treble=g=3",
        "description": "Aksiyon — bass boost",
    },
    "satella": {
        "music_volume": 0.05,
        "dialogue_volume": 1.8,
        "filter": "aecho=0.9:0.9:100:0.6,lowpass=f=2000",
        "description": "Satella — derin echo",
    },
    "dialogue": {
        "music_volume": 0.12,
        "dialogue_volume": 1.2,
        "filter": "equalizer=f=1000:width_type=o:width=2:g=2",
        "description": "Diyalog — müzik arka planda",
    },
    "default": {
        "music_volume": 0.35,
        "dialogue_volume": 1.0,
        "filter": None,
        "description": "Normal",
    },
}


def get_sfx_preset(clip: dict) -> dict:
    mood = clip.get("lore_mood", clip.get("scene_type", "default"))
    lore_desc = clip.get("lore_desc", "")
    importance = clip.get("lore_importance", 0)
    motion = clip.get("motion_score", 0)

    desc_lower = lore_desc.lower() if lore_desc else ""
    if any(w in desc_lower for w in ["ölüm", "death", "dies", "killed", "return by death"]):
        return SFX_PRESETS["death"]
    if any(w in desc_lower for w in ["satella", "witch", "envy"]):
        return SFX_PRESETS["satella"]
    if importance >= 9 or mood == "emotional":
        return SFX_PRESETS["emotional"]
    if mood == "action" or motion >= 7:
        return SFX_PRESETS["action"]
    if clip.get("has_dialogue"):
        return SFX_PRESETS["dialogue"]

    return SFX_PRESETS["default"]


def apply_sfx(clip_path: str, music_path: str, clip: dict, output_path: str) -> str:
    preset = get_sfx_preset(clip)
    mv = preset["music_volume"]
    dv = preset["dialogue_volume"]
    af = preset["filter"]

    filters = []
    if af:
        filters.append(f"[0:a]{af}[dialogue]")
    else:
        filters.append(f"[0:a]volume={dv}[dialogue]")

    has_music = music_path and Path(music_path).exists()

    if has_music:
        filters.append(f"[1:a]volume={mv}[music]")
        filters.append("[dialogue][music]amix=inputs=2:duration=first[aout]")

        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-i", music_path,
            "-filter_complex", ";".join(filters),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
    else:
        filters.append("[dialogue]aformat=sample_rates=48000:channel_layouts=stereo[aout]")
        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-filter_complex", ";".join(filters),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy(clip_path, output_path)

    return output_path
