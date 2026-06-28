"""editor/timeline.py birim testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from editor.timeline import Timeline, create_timeline


class TestTimeline:
    def test_init_defaults(self):
        t = Timeline()
        assert t.fps == 30
        assert t.width == 1080
        assert t.height == 1920
        assert t.clips == []

    def test_add_clip(self):
        t = Timeline()
        clip = {"id": 1, "duration": 3}
        t.add_clip(clip)
        assert len(t.clips) == 1

    def test_to_json_structure(self):
        t = Timeline(fps=24, width=1920, height=1080)
        t.add_clip({"id": 1})
        data = t.to_json()
        assert data["fps"] == 24
        assert data["resolution"] == [1920, 1080]
        assert len(data["clips"]) == 1


class TestCreateTimeline:
    def test_creates_timeline_with_clips(self):
        clips = [{"id": 1}, {"id": 2}]
        t = create_timeline(clips)
        assert len(t.clips) == 2

    def test_uses_config(self):
        clips = [{"id": 1}]
        config = {"resolution": [720, 1280], "fps": 60}
        t = create_timeline(clips, output_config=config)
        data = t.to_json()
        assert data["fps"] == 60
        assert data["resolution"] == [720, 1280]
