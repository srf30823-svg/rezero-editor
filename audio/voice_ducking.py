"""Audio ducking: lower music when dialogue is detected."""
import subprocess
import tempfile
import os
from pathlib import Path


def apply_ducking(
    video_path: str,
    music_path: str,
    output_path: str,
    dialogue_volume: float = 1.0,
    music_volume_normal: float = 0.6,
    music_volume_ducked: float = 0.15,
    duck_threshold: float = -30.0,
) -> str:
    """
    Mixes video audio (dialogue) with music.
    Music is automatically ducked when dialogue is detected.

    Args:
        video_path: Source video with original audio (character voices)
        music_path: Background music MP3
        output_path: Output MP4 path
        dialogue_volume: Character voice volume (1.0 = original)
        music_volume_normal: Music volume during silence
        music_volume_ducked: Music volume during dialogue
        duck_threshold: dB threshold for dialogue detection

    Returns:
        Output path
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    filter_complex = (
        f"[0:a]volume={dialogue_volume}[voice];"
        f"[1:a]volume={music_volume_normal}[music_in];"
        f"[voice]asplit=2[voice_out][voice_sc];"
        f"[music_in][voice_sc]sidechaincompress="
        f"threshold={duck_threshold}dB:"
        f"ratio=4:attack=200:release=1000:"
        f"level_sc=0.8[music_ducked];"
        f"[voice_out][music_ducked]amix=inputs=2:duration=first[audio_out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[audio_out]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        fallback_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            f"[0:a]volume={dialogue_volume}[v];[1:a]volume={music_volume_ducked}[m];[v][m]amix=inputs=2:duration=first[out]",
            "-map", "0:v",
            "-map", "[out]",
            "-c:v", "copy",
            "-c:a", "aac",
            output_path
        ]
        result2 = subprocess.run(fallback_cmd, capture_output=True, text=True)
        if result2.returncode != 0:
            raise RuntimeError(f"Ses karıştırma hatası: {result2.stderr[-500:]}")

    return output_path
