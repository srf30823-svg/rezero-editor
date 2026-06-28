"""Re:Zero lore sorgu motoru - karakter ve arc bilgilerini sağlar."""
import json
from pathlib import Path
from typing import Optional

CHARACTERS_PATH = Path(__file__).parent / "characters.json"
ARCS_PATH = Path(__file__).parent / "arcs.json"
MOMENTS_PATH = Path(__file__).parent / "moments.json"


def _load_json(path: Path) -> dict:
    """JSON dosyasını yükler."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_character_score(name: str) -> dict:
    """
    Belirli bir karakterin puanlarını döndürür.
    
    Args:
        name: Aranan karakterin adı (tam ad veya takma ad)
    
    Returns:
        Karakter puanları ve bilgileri içeren dict
    """
    data = _load_json(CHARACTERS_PATH)
    name_lower = name.lower()
    
    for char_key, char_data in data["characters"].items():
        if char_key.lower() == name_lower:
            return char_data
        if any(alias.lower() == name_lower for alias in char_data.get("aliases", [])):
            return char_data
    
    return {"error": f"Karakter '{name}' bulunamadı"}


def get_arc_info(arc_number: int) -> dict:
    """
    Belirli bir arcanın bilgilerini döndürür.
    
    Args:
        arc_number: Arc numarası (1-6)
    
    Returns:
        Arc bilgileri içeren dict
    """
    data = _load_json(ARCS_PATH)
    arc_key = str(arc_number)
    
    if arc_key not in data["arcs"]:
        return {"error": f"Arc {arc_number} bulunamadı"}
    
    return data["arcs"][arc_key]


def classify_scene(intensity: float, duration: float) -> str:
    """
    Sahnenin türünü belirler.
    
    Args:
        intensity: Sahnenin yoğunluğu (0-10 arası)
        duration: Sahnenin süresi (saniye)
    
    Returns:
        Sahne türü: action, emotional, dialogue, or atmospheric
    """
    if intensity >= 7:
        return "action"
    elif intensity >= 4:
        return "emotional"
    elif duration > 10:
        return "dialogue"
    else:
        return "atmospheric"


def get_top_characters(n: int = 5) -> list:
    """
    Fan favori skorlarına göre en iyi karakterleri döndürür.
    
    Args:
        n: Döndürülecek karakter sayısı
    
    Returns:
        En iyi karakterlerin listesi
    """
    data = _load_json(CHARACTERS_PATH)
    
    sorted_chars = sorted(
        data["characters"].items(),
        key=lambda x: x[1].get("fan_favorite_score", 0),
        reverse=True
    )
    
    return [{"key": k, **v} for k, v in sorted_chars[:n]]


def get_moments_by_arc(arc_number: int) -> list:
    """
    Belirli bir arca göre sahneleri getirir.
    
    Args:
        arc_number: Arc numarası
    
    Returns:
        O araca ait sahnelerin listesi
    """
    data = _load_json(MOMENTS_PATH)
    return [m for m in data.get("moments", []) if m.get("arc") == arc_number]


def get_moments_by_character(character_name: str) -> list:
    """
    Belirli bir karaktere göre sahneleri getirir.
    
    Args:
        character_name: Karakter adı
    
    Returns:
        O karaktere ait sahnelerin listesi
    """
    data = _load_json(MOMENTS_PATH)
    return [m for m in data.get("moments", []) 
            if character_name in m.get("characters", [])]