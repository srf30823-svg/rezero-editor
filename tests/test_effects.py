"""editor/effects.py birim testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from editor.effects import apply_effects


class TestApplyEffects:
    def test_action_effects(self):
        clip = {"scene_type": "action", "intensity": 7}
        result = apply_effects(clip)
        assert "zoom" in result.get("effects", [])
        assert "flash" in result.get("effects", [])

    def test_emotional_effects(self):
        clip = {"scene_type": "emotional", "intensity": 6}
        result = apply_effects(clip)
        assert "warm_grade" in result.get("effects", [])

    def test_dialogue_effects(self):
        clip = {"scene_type": "dialogue", "intensity": 3}
        result = apply_effects(clip)
        assert "natural_grade" in result.get("effects", [])

    def test_does_not_mutate_original_keys(self):
        clip = {"scene_type": "action", "intensity": 8, "source": "test.mp4"}
        result = apply_effects(clip)
        assert result["source"] == "test.mp4"
