"""knowledge/lore_engine.py birim testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.lore_engine import (
    get_character_score,
    get_arc_info,
    classify_scene,
    get_top_characters,
    get_moments_by_arc,
    get_moments_by_character,
)


class TestGetCharacterScore:
    def test_rem_exists(self):
        data = get_character_score("rem")
        assert "error" not in data
        assert "fan_favorite_score" in data

    def test_subaru_exists(self):
        data = get_character_score("subaru")
        assert "error" not in data

    def test_unknown_character(self):
        data = get_character_score("unknown_xyz")
        assert "error" in data

    def test_alias_lookup(self):
        data = get_character_score("rem")
        assert data.get("fan_favorite_score", 0) > 0


class TestGetArcInfo:
    def test_arc_1_exists(self):
        data = get_arc_info(1)
        assert "error" not in data

    def test_invalid_arc(self):
        data = get_arc_info(99)
        assert "error" in data


class TestClassifyScene:
    def test_action(self):
        assert classify_scene(8.0, 5.0) == "action"

    def test_emotional(self):
        assert classify_scene(5.0, 5.0) == "emotional"

    def test_dialogue(self):
        assert classify_scene(2.0, 15.0) == "dialogue"

    def test_atmospheric(self):
        assert classify_scene(2.0, 5.0) == "atmospheric"


class TestGetTopCharacters:
    def test_returns_list(self):
        result = get_top_characters(3)
        assert len(result) == 3

    def test_top_has_rem(self):
        result = get_top_characters(5)
        names = [c["key"] for c in result]
        assert "Rem" in names


class TestGetMomentsByArc:
    def test_returns_list(self):
        result = get_moments_by_arc(1)
        assert isinstance(result, list)


class TestGetMomentsByCharacter:
    def test_returns_list(self):
        result = get_moments_by_character("Rem")
        assert isinstance(result, list)
