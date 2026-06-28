"""Otomatik altyazı motoru - SRT/ASS üretimi ve karakter etiketleme."""
from typing import Dict, List, Optional
from pathlib import Path


CAPTION_TEXTS = {
    "action": {
        "tr": ["⚡ Aksiyon!", "Savaş!", "Çarpışma!", "Mücadele!", "Darbe!"],
        "en": ["⚡ Action!", "Battle!", "Clash!", "Struggle!", "Strike!"],
    },
    "emotional": {
        "tr": ["Duygusal An", "Gözyaşı Anı", "Kalp Kırıklığı", "Veda", "Kavuşma"],
        "en": ["Emotional Moment", "Tearjerker", "Heartbreak", "Farewell", "Reunion"],
    },
    "dialogue": {
        "tr": ["Konuşma", "Diyalog", "Sohbet", "Tartışma", "İtiraf"],
        "en": ["Conversation", "Dialogue", "Chat", "Argument", "Confession"],
    },
    "atmospheric": {
        "tr": ["Büyüleyici", "Gizemli", "Sürükleyici", "Huzurlu", "Karanlık"],
        "en": ["Enchanting", "Mysterious", "Immersive", "Peaceful", "Dark"],
    },
}

TOP_CHARACTERS = ["Rem", "Subaru", "Emilia", "Beatrice", "Echidna", "Ram", "Roswaal", "Otto", "Garfiel", "Petra"]


def generate_captions(clips: List[Dict], language: str = "tr") -> List[Dict]:
    """
    Video kliplere sahne türüne göre altyazı üretir.

    Args:
        clips: Klip listesi
        language: Altyazı dili (tr/en)

    Returns:
        Altyazı eklenmiş klip listesi
    """
    for clip in clips:
        scene_type = clip.get("scene_type", "dialogue")
        intensity = clip.get("intensity", 5)
        duration = clip.get("duration", 3)
        characters = identify_characters(clip)

        captions = []

        if characters:
            name_text = " / ".join(characters[:2])
            captions.append({"text": name_text, "start": 0.0, "end": min(1.5, duration)})

        texts = CAPTION_TEXTS.get(scene_type, CAPTION_TEXTS["dialogue"])
        lang_texts = texts.get(language, texts["en"])
        caption_text = lang_texts[int(intensity) % len(lang_texts)]

        captions.append({
            "text": caption_text,
            "start": max(0.5, duration * 0.2),
            "end": min(duration - 0.3, duration * 0.7),
        })

        clip["captions"] = captions

    return clips


def identify_characters(clip: Dict) -> List[str]:
    """
    Klip içinde geçen karakterleri belirler.

    Args:
        clip: Klip verisi

    Returns:
        Karakter isimleri listesi
    """
    frame_path = str(clip.get("frame_path", ""))
    return [c for c in TOP_CHARACTERS if c.lower() in frame_path.lower()]


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


def generate_srt(clips: List[Dict], global_offset: float = 0.0) -> str:
    """
    Tüm klipler için SRT altyazı dosyası üretir.

    Args:
        clips: Altyazılı klip listesi
        global_offset: Tüm zamanlara eklenecek offset (saniye)

    Returns:
        SRT formatında altyazı metni
    """
    lines = []
    subtitle_index = 1
    running_time = global_offset

    for clip in clips:
        duration = clip.get("duration", 3)
        captions = clip.get("captions", [])

        for caption in captions:
            start = running_time + caption.get("start", 0)
            end = running_time + caption.get("end", duration)
            text = caption.get("text", "")

            lines.append(str(subtitle_index))
            lines.append(f"{_srt_time(start)} --> {_srt_time(end)}")
            lines.append(text)
            lines.append("")
            subtitle_index += 1

        running_time += duration

    return "\n".join(lines)


def _srt_time(seconds: float) -> str:
    """Saniyeyi SRT zaman formatına çevirir (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_ass_style_block() -> str:
    """
    ASS formatı için stil bloğu üretir.

    Returns:
        ASS stil tanımı
    """
    return (
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: TopCaption, Arial, 28, &H00FFFFFF, &H000000FF, "
        "&H00000000, &H80000000, -1, 0, 0, 0, "
        "100, 100, 0, 0, 1, 2, 1, 8, 10, 10, 40, 1\n"
        "Style: BottomCaption, Arial, 24, &H00FFFFFF, &H000000FF, "
        "&H00000000, &H80000000, -1, 0, 0, 0, "
        "100, 100, 0, 0, 1, 2, 1, 2, 10, 10, 40, 1\n"
    )


def generate_ass(clips: List[Dict], global_offset: float = 0.0) -> str:
    """
    Tüm klipler için ASS altyazı dosyası üretir.

    Args:
        clips: Altyazılı klip listesi
        global_offset: Tüm zamanlara eklenecek offset (saniye)

    Returns:
        ASS formatında altyazı metni
    """
    output = ["[Script Info]", "Title: RE:Zero Shorts Captions",
              "ScriptType: v4.00+", "WrapStyle: 0", "ScaledBorderAndShadow: yes",
              "PlayResX: 1080", "PlayResY: 1920", ""]
    output.append(generate_ass_style_block())
    output.append("[Events]")
    output.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    running_time = global_offset

    for clip in clips:
        duration = clip.get("duration", 3)
        captions = clip.get("captions", [])

        for caption in captions:
            start = running_time + caption.get("start", 0)
            end = running_time + caption.get("end", duration)
            text = caption.get("text", "")
            style = "TopCaption" if caption.get("start", 0) == 0.0 else "BottomCaption"

            ass_text = text.replace("{", "\\{").replace("}", "\\}")
            output.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},"
                f"{style},,0,0,0,,{ass_text}"
            )

        running_time += duration

    return "\n".join(output)


def _ass_time(seconds: float) -> str:
    """Saniyeyi ASS zaman formatına çevirir (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
