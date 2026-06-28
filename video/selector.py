"""En iyi klipleri seçen motor."""
from typing import List, Dict


def select_clips(scenes: List[Dict], 
                 min_duration: float = 1.5,
                 max_duration: float = 8.0,
                 target_duration: float = 59.0) -> List[Dict]:
    """
    Hedef süreye göre en iyi klipleri seçer.
    
    Args:
        scenes: Puanlanmış sahneler listesi
        min_duration: Minimum klip süresi
        max_duration: Maksimum klip süresi
        target_duration: Hedef toplam süre
    
    Returns:
        Seçilen klip listesi
    """
    sorted_scenes = sorted(scenes, key=lambda x: x.get("content_value", 0), reverse=True)
    
    selected = []
    total_time = 0.0
    
    for scene in sorted_scenes:
        duration = min(max_duration, max(min_duration, scene.get("intensity", 5) / 2))
        
        if total_time + duration <= target_duration:
            selected.append({
                **scene,
                "duration": duration
            })
            total_time += duration
    
    return selected