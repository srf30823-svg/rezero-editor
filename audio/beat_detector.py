"""librosa-based beat detection with caching."""
import librosa
import numpy as np
from typing import Dict, List
from pathlib import Path

_beat_cache: Dict[str, dict] = {}


def detect_beats(audio_path: str, sample_rate: int = 22050) -> dict:
    """
    Detect beats and drop points in an audio file.

    Args:
        audio_path: Path to the audio file.
        sample_rate: Target sample rate for analysis.

    Returns:
        Dict with BPM, beat_times, drop_times, and duration.
    """
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Ses dosyası bulunamadı: {audio_path}")

    cache_key = str(Path(audio_path).resolve())
    if cache_key in _beat_cache:
        return _beat_cache[cache_key]

    try:
        y, sr = librosa.load(audio_path, sr=sample_rate)
    except Exception as e:
        raise RuntimeError(f"Ses dosyası okunamadı: {audio_path} - {e}") from e

    if len(y) == 0:
        raise ValueError("Ses dosyası boş veya okunamadı")

    duration = len(y) / sr

    # Handle silence / pure noise: if RMS is extremely low, return empty beats.
    rms = librosa.feature.rms(y=y)[0]
    if np.max(rms) < 1e-5:
        result = {
            "bpm": 0.0,
            "beat_times": [],
            "drop_times": [],
            "duration": duration,
        }
        _beat_cache[cache_key] = result
        return result

    try:
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    except Exception as e:
        raise RuntimeError(f"Beat tespiti başarısız: {e}") from e

    beat_times_list = beat_times.tolist() if hasattr(beat_times, "tolist") else list(beat_times)
    drop_times = detect_drops(y, sr, beat_times_list)

    result = {
        "bpm": float(tempo),
        "beat_times": beat_times_list[:100],
        "drop_times": drop_times,
        "duration": duration,
    }
    _beat_cache[cache_key] = result
    return result


def detect_drops(y: np.ndarray, sr: float, beat_times: List[float]) -> List[float]:
    """
    Detect drop points (sudden energy changes) in the audio signal.

    Args:
        y: Audio waveform.
        sr: Sample rate.
        beat_times: Detected beat times.

    Returns:
        List of drop times.
    """
    drops = []

    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)

    for i in range(1, len(rms) - 1):
        if rms[i] > rms[i - 1] * 1.5 and rms[i] > rms[i + 1] * 1.5:
            drops.append(float(rms_times[i]))

    return drops[:10]
