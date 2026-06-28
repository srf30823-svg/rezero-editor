"""Sahne puanlama motoru."""
from knowledge.lore_engine import get_character_score, classify_scene


def score_scenes(scenes: list, boost_multiplier: float = 1.4) -> list:
    """
    Sahnelere puan verir.
    
    Args:
        scenes: Analiz edilmiş sahneler listesi
        boost_multiplier: Aksiyon sahneleri için çarpan
    
    Returns:
        Puanlanmış sahneler listesi
    """
    scored = []
    
    for scene in scenes:
        intensity = scene.get("motion_level", 0)
        scene_type = classify_scene(intensity, 5.0)
        
        if scene_type == "action":
            intensity = min(intensity * boost_multiplier, 10.0)
        
        scored.append({
            **scene,
            "intensity": round(intensity, 2),
            "scene_type": scene_type,
            "content_value": determine_content_value(scene)
        })
    
    return scored


def determine_content_value(scene: dict) -> float:
    """
    Sahnenin içerik değerini belirler.
    
    Args:
        scene: Sahne verisi
    
    Returns:
        İçerik değer skoru
    """
    base_score = scene.get("intensity", 0)
    
    # Re:Zero özel sahne bonusları
    if "Rem" in str(scene.get("frame_path", "")):
        base_score += 2.0
    if "Subaru" in str(scene.get("frame_path", "")):
        base_score += 1.5
    if "Echidna" in str(scene.get("frame_path", "")):
        base_score += 2.5
    
    return min(base_score, 10.0)