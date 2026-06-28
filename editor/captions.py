"""Otomatik altyazı motoru."""
from typing import Dict, List


def generate_captions(clips: List[Dict], language: str = "tr") -> List[Dict]:
    """
    Videokliplere altyazı ekler.
    
    Args:
        clips: Klip listesi
        language: Altyazı dili
    
    Returns:
        Altyazı eklenmiş klip listesi
    """
    for clip in clips:
        captions = []
        
        if "Rem" in str(clip.get("frame_path", "")):
            captions.append({"text": "Rem", "start": 0, "end": 2})
        if "Subaru" in str(clip.get("frame_path", "")):
            captions.append({"text": "Subaru", "start": 0, "end": 2})
        
        clip["captions"] = captions
    
    return clips


def add_character_tags(clip: Dict) -> str:
    """
    Klip için karakter etiketi oluşturur.
    
    Args:
        clip: Klip verisi
    
    Returns:
        Altyazı metni
    """
    characters = identify_characters(clip)
    return " / ".join(characters) if characters else ""


def identify_characters(clip: Dict) -> List[str]:
    """
    Klip içinde geçen karakterleri belirler.
    
    Args:
        clip: Klip verisi
    
    Returns:
        Karakter isimleri listesi
    """
    frame_path = str(clip.get("frame_path", ""))
    top_chars = ["Rem", "Subaru", "Emilia", "Beatrice", "Echidna"]
    return [c for c in top_chars if c in frame_path]