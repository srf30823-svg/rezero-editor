"""Sahne puanlama motoru."""
from knowledge.lore_engine import get_character_score, get_arc_info, classify_scene
from pathlib import Path
import json


def score_scenes(scenes: list, boost_multiplier: float = 1.4, config: dict = None) -> list:
    """
    Sahnelere puan verir.
    
    Args:
        scenes: Analiz edilmiş sahneler listesi
        boost_multiplier: Aksiyon sahneleri için çarpan
        config: Konfigürasyon ayarları
    
    Returns:
        Puanlanmış sahneler listesi
    """
    config = config or {"action_boost_multiplier": 1.4}
    multiplier = config.get("action_boost_multiplier", boost_multiplier)
    
    scored = []
    
    for scene in scenes:
        intensity = scene.get("motion_level", 0) / 10
        scene_type = classify_scene(scene.get("motion_level", 0), 5.0)
        
        if scene_type == "action":
            intensity = min(intensity * multiplier, 10.0)
        
        scored.append({
            **scene,
            "intensity": round(intensity, 2),
            "scene_type": scene_type,
            "content_value": determine_content_value(scene),
            "emotion_score": calculate_emotion_score(scene)
        })
    
    return scored


def determine_content_value(scene: dict) -> float:
    """
    Sahnenin içerik değerini belirler.
    
    Args:
        scene: Sahne verisi
    
    Returns:
        İçerik değer skoru (0-10)
    """
    base_score = scene.get("intensity", 0)
    frame_path = str(scene.get("frame_path", ""))
    
    character_bonuses = {
        "rem": 2.0, "rem_": 2.0,
        "subaru": 1.5, "subaru_": 1.5,
        "emilia": 1.2, "emilia_": 1.2,
        "beatrice": 1.0, "beatrice_": 1.0,
        "echidna": 2.5, "echidna_": 2.5,
        "elsa": 1.5, "elsa_": 1.5
    }
    
    for key, bonus in character_bonuses.items():
        if key in frame_path.lower():
            base_score += bonus
            break
    
    return min(base_score, 10.0)


def calculate_emotion_score(scene: dict) -> float:
    """
    Sahne için duygu skorunu hesaplar.
    
    Args:
        scene: Sahne verisi
    
    Returns:
        Duygu skoru (0-10)
    """
    intensity = scene.get("intensity", 0)
    scene_type = scene.get("scene_type", "dialogue")
    
    emotion_map = {
        "action": 7.0,
        "emotional": 9.0,
        "dialogue": 5.0,
        "atmospheric": 4.0
    }
    
    base = emotion_map.get(scene_type, 5.0)
    return min(base + intensity * 0.5, 10.0)


def score_character_scene(frame_path: str, characters: list = None) -> float:
    """
    Karakter tespitine göre sahne puanını hesaplar.
    
    Args:
        frame_path: Çerçeve dosyası yolu
        characters: Kontrol edilecek karakterler listesi
    
    Returns:
        Karakter puanı
    """
    characters = characters or ["rem", "subaru", "emilia", "echidna", "beatrice"]
    frame_lower = Path(frame_path).stem.lower()
    
    total_score = 0.0
    for char in characters:
        if char in frame_lower:
            char_data = get_character_score(char)
            total_score += char_data.get("fan_favorite_score", 0)
    
    return total_score