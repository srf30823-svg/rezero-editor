"""Beat'e senkronize kesim motoru."""
from typing import List, Dict


def sync_to_beats(clips: List[Dict], beat_times: List[float], drop_times: List[float]) -> List[Dict]:
    """
    Klipleri beat zamanlarına göre hizalar.
    
    Args:
        clips: Seçilen klip listesi
        beat_times: Beat zamanları
        drop_times: Drop zamanları
    
    Returns:
        Hizalanmış klip listesi
    """
    synced = []
    
    for clip in clips:
        start_time = find_nearest_beat(clip.get("timestamp", 0), beat_times)
        
        synced.append({
            **clip,
            "start_time": start_time,
            "sync_type": "beat" if start_time in beat_times else "drop"
        })
    
    return synced


def find_nearest_beat(timestamp: float, beat_times: List[float]) -> float:
    """
    En yakın beat zamanını bulur.
    
    Args:
        timestamp: İstenen zaman
        beat_times: Beat zamanları
    
    Returns:
        En yakın beat zamanı
    """
    if not beat_times:
        return timestamp
    
    return min(beat_times, key=lambda b: abs(b - timestamp))