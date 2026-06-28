"""editor/captions.py birim testleri."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from editor.captions import (
    generate_captions,
    identify_characters,
    add_character_tags,
    generate_srt,
    generate_ass,
)


def _make_clip(scene_type="dialogue", intensity=5, duration=3,
               frame_path="frame_001.jpg", start_time=0.0):
    return {
        "scene_type": scene_type,
        "intensity": intensity,
        "duration": duration,
        "frame_path": frame_path,
        "start_time": start_time,
    }


class TestIdentifyCharacters:
    def test_rem_detected(self):
        clip = _make_clip(frame_path="episode_rem_fight_001.jpg")
        assert "Rem" in identify_characters(clip)

    def test_subaru_detected(self):
        clip = _make_clip(frame_path="subaru_cry_scene.jpg")
        assert "Subaru" in identify_characters(clip)

    def test_no_character(self):
        clip = _make_clip(frame_path="landscape_view.jpg")
        assert identify_characters(clip) == []

    def test_multiple_characters(self):
        clip = _make_clip(frame_path="rem_and_subaru_talk.jpg")
        chars = identify_characters(clip)
        assert "Rem" in chars
        assert "Subaru" in chars


class TestAddCharacterTags:
    def test_with_rem(self):
        clip = _make_clip(frame_path="rem_smile.jpg")
        assert "Rem" in add_character_tags(clip)

    def test_empty_when_no_char(self):
        clip = _make_clip(frame_path="forest_bg.jpg")
        assert add_character_tags(clip) == ""


class TestGenerateCaptions:
    def test_action_has_captions(self):
        clips = [_make_clip(scene_type="action", intensity=8)]
        result = generate_captions(clips, language="tr")
        assert len(result[0]["captions"]) >= 1

    def test_emotional_has_captions(self):
        clips = [_make_clip(scene_type="emotional")]
        result = generate_captions(clips, language="tr")
        assert len(result[0]["captions"]) >= 1

    def test_dialogue_has_captions(self):
        clips = [_make_clip(scene_type="dialogue")]
        result = generate_captions(clips, language="tr")
        assert len(result[0]["captions"]) >= 1

    def test_english_language(self):
        clips = [_make_clip(scene_type="action", intensity=5)]
        result = generate_captions(clips, language="en")
        texts = [c["text"] for c in result[0]["captions"]]
        assert any("Action" in t for t in texts)

    def test_turkish_language(self):
        clips = [_make_clip(scene_type="action", intensity=5)]
        result = generate_captions(clips, language="tr")
        texts = [c["text"] for c in result[0]["captions"]]
        assert any("Aksiyon" in t for t in texts)

    def test_character_name_in_captions(self):
        clips = [_make_clip(frame_path="rem_battle.jpg", scene_type="action")]
        result = generate_captions(clips, language="tr")
        caption_texts = [c["text"] for c in result[0]["captions"]]
        assert any("Rem" in t for t in caption_texts)


class TestGenerateSrt:
    def test_basic_srt_structure(self):
        clips = [_make_clip(scene_type="action", duration=3)]
        captioned = generate_captions(clips)
        srt = generate_srt(captioned)
        assert "1" in srt
        assert "-->" in srt

    def test_multiple_clips(self):
        clips = [
            _make_clip(scene_type="action", duration=2),
            _make_clip(scene_type="emotional", duration=3),
        ]
        captioned = generate_captions(clips)
        srt = generate_srt(captioned)
        lines = srt.strip().split("\n")
        assert lines[0].isdigit()

    def test_global_offset(self):
        clips = [_make_clip(scene_type="dialogue", duration=3)]
        captioned = generate_captions(clips)
        srt = generate_srt(captioned, global_offset=10.0)
        assert "00:00:10" in srt


class TestGenerateAss:
    def test_basic_ass_structure(self):
        clips = [_make_clip(scene_type="action")]
        captioned = generate_captions(clips)
        ass = generate_ass(captioned)
        assert "[Script Info]" in ass
        assert "[V4+ Styles]" in ass
        assert "[Events]" in ass
        assert "Dialogue:" in ass

    def test_multiple_clips_ass(self):
        clips = [
            _make_clip(scene_type="action", duration=2),
            _make_clip(scene_type="dialogue", duration=3),
        ]
        captioned = generate_captions(clips)
        ass = generate_ass(captioned)
        assert ass.count("Dialogue:") >= 2
