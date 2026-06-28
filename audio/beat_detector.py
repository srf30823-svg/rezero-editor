"""librosa tabanlı beat tespiti."""
import librosa
import numpy as np


def detect_beats(audio_path: str) -> dict:
    """
    Müzik dosyasından beat ve drop noktalarını tespit eder.
    
    Args:
        audio_path: Müzik dosyası yolu
    
    Returns:
        BPM, beat_zamanları ve drop_zamanları içeren dict
    """
    y, sr = librosa.load(audio_path)
    
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    
    drop_times = detect_drops(y, sr, beat_times)
    
    return {
        "bpm": float(tempo),
        "beat_times": beat_times.tolist()[:100],
        "drop_times": drop_times,
        "duration": len(y) / sr
    }


def detect_drops(y: np.ndarray, sr: float, beat_times: np.ndarray) -> list:
    """
    Drop (basmaya) noktalarını tespit eder.
    
    Args:
        y: Ses dalgası
        sr: Örnekleme hızı
        beat_times: Beat zamanları
    
    Returns:
        Drop zamanları listesi
    """
    drops = []
    
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)
    
    for i in range(1, len(rms) - 1):
        if rms[i] < rms[i-1] * 0.3 and rms[i] < rms[i+1] * 0.3:
            drops.append(float(rms_times[i]))
    
    return drops[:10]