"""FFmpeg-based render engine with Ken Burns, xfade transitions, color grading."""
import subprocess
import json
import tempfile
import shutil
import os
from pathlib import Path
from typing import Optional, Union, List

from audio.music_selector import select_music, analyze_clips_mood, get_music_dir
from audio.voice_ducking import apply_ducking
from knowledge.owl_director import direct_edit_owl
from rich.console import Console

console = Console()

TRANSITION_DURATION = 0.35
FPS = 30
WIDTH = 1080
HEIGHT = 1920

XFADE_MAP = {
    ("action", "action"): "fadeblack",
    ("action", "dialogue"): "fade",
    ("action", "emotional"): "fadeblack",
    ("dialogue", "action"): "slideleft",
    ("dialogue", "dialogue"): "dissolve",
    ("dialogue", "emotional"): "fade",
    ("emotional", "action"): "fadeblack",
    ("emotional", "emotional"): "dissolve",
    ("emotional", "dialogue"): "fade",
}

COLOR_GRADE_MAP = {
    "action": "eq=saturation=1.4:contrast=1.15:brightness=0.03",
    "emotional": "eq=saturation=1.1:contrast=1.0:brightness=0.08",
    "dialogue": "eq=saturation=1.0:contrast=1.0:brightness=0.0",
    "atmospheric": "eq=saturation=0.8:contrast=1.2:brightness=-0.05",
}


def render_shorts(timeline: Union[dict, str], output_path: str,
                  music_path: Optional[str] = None,
                  subtitle_path: Optional[str] = None,
                  preserve_dialogue: bool = True,
                  use_llm: bool = True,
                  beat_times: Optional[List[float]] = None) -> str:
    if isinstance(timeline, (str, Path)):
        p = Path(timeline)
        if not p.exists():
            raise FileNotFoundError(f"Timeline dosyası bulunamadı: {timeline}")
        with open(p, "r", encoding="utf-8") as f:
            timeline = json.load(f)

    clips = timeline.get("clips", [])
    if not clips:
        raise ValueError("Timeline'de klip bulunamadı")

    if use_llm:
        music_dir = get_music_dir()
        available_music = [f.name for f in Path(music_dir).rglob("*.mp3")] if music_dir.exists() else []
        edit_plan = direct_edit_owl(clips, available_music)
        ordered_ids = edit_plan.get("ordered_clip_ids", list(range(len(clips))))
        clips = [clips[i] for i in ordered_ids if i < len(clips)]
        if not music_path and edit_plan.get("music_track") and available_music:
            for f in Path(music_dir).rglob("*.mp3"):
                if f.name == edit_plan["music_track"]:
                    music_path = str(f)
                    break
        console.print(f"[cyan]🦉 Owl Director: {edit_plan.get('reasoning', 'Edit planı oluşturuldu')}[/cyan]")

    if music_path is None:
        mood = analyze_clips_mood(clips)
        music_path = select_music(mood)
        console.print(f"[cyan]♪ Otomatik müzik seçildi ({mood}): {Path(music_path).name}[/cyan]")

    output_dir = Path(output_path).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(exist_ok=True, parents=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="rezero_render_"))

    try:
        clip_paths = []
        durations = []
        scene_types = []
        for i, clip in enumerate(clips):
            p, dur = _render_clip(clip, i, temp_dir)
            clip_paths.append(p)
            durations.append(dur)
            scene_types.append(clip.get("scene_type", "dialogue"))

        if len(clip_paths) == 1:
            merged = temp_dir / "merged.mp4"
            shutil.copy(clip_paths[0], merged)
        else:
            merged = temp_dir / "merged.mp4"
            _concat_xfade(clip_paths, durations, merged, scene_types=scene_types)

        current = merged

        if subtitle_path and Path(subtitle_path).exists():
            subtitled = temp_dir / "subtitled.mp4"
            sub_cmd = [
                "ffmpeg", "-i", str(current),
                "-vf", f"subtitles={_escape_path(subtitle_path)}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-preset", "fast", "-crf", "23",
                "-y", str(subtitled),
            ]
            _run_ffmpeg(sub_cmd, "Altyazı yakma")
            current = subtitled

        if music_path and Path(music_path).exists():
            mixed = temp_dir / "final.mp4"
            if preserve_dialogue:
                try:
                    apply_ducking(
                        str(current), music_path, str(mixed),
                        dialogue_volume=1.0,
                        music_volume_normal=0.6,
                        music_volume_ducked=0.15,
                    )
                except RuntimeError as e:
                    console.print(f"[yellow]⚠ Ducking başarısız, basit karışıma dönülüyor: {e}[/yellow]")
                    preserve_dialogue = False
            if not preserve_dialogue:
                audio_cmd = [
                    "ffmpeg", "-i", str(current), "-i", music_path,
                    "-filter_complex",
                    "[0:a]volume=1.0[v];[1:a]volume=0.5[m];[v][m]amix=inputs=2:duration=first[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac",
                    "-y", str(mixed),
                ]
                _run_ffmpeg(audio_cmd, "Ses karıştırma")
            current = mixed

        shutil.move(str(current), output_path)

    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

    return output_path


def _render_clip(clip: dict, index: int, temp_dir: Path) -> tuple:
    """Render a single clip with Ken Burns zoom and color grading.
    Returns (output_path, actual_duration)."""
    source = clip.get("source", "")
    if not source or not Path(source).exists():
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {source}")

    start = float(clip.get("start_time", 0.0))
    duration = float(clip.get("actual_duration", clip.get("duration", 3.0)))
    if duration <= 0:
        raise ValueError(f"Geçersiz süre: {duration}")

    scene_type = clip.get("scene_type", "dialogue")
    output_path = str(temp_dir / f"clip_{index:04d}.mp4")

    filters = []

    # Scale + pad to 1080x1920
    filters.append(
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black"
    )

    # Ken Burns zoom (alternate in/out)
    nframes = int(duration * FPS)
    if nframes < 2:
        nframes = 2
    speed = 0.0006
    if index % 2 == 0:
        zoom_expr = f"if(eq(on,1),1.0,zoom+{speed})"
    else:
        zoom_expr = f"if(eq(on,1),1.08,zoom-{speed})"
    filters.append(
        f"zoompan=z='{zoom_expr}':d={nframes}:fps={FPS}:s={WIDTH}x{HEIGHT}"
    )

    # Color grading
    grade = COLOR_GRADE_MAP.get(scene_type)
    if grade:
        filters.append(grade)

    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", source,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "26",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        output_path,
    ]

    _run_ffmpeg(cmd, f"Klip {index} render")

    return output_path, duration


def _concat_xfade(clip_paths: List[str], durations: List[float],
                  output_path: Path, transition_dur: float = TRANSITION_DURATION,
                  scene_types: Optional[List[str]] = None):
    """Chain clips with xfade + acrossfade transitions (pair-wise)."""
    n = len(clip_paths)
    if n == 1:
        shutil.copy(clip_paths[0], output_path)
        return

    st = scene_types or [""] * n
    current = clip_paths[:]
    current_dur = durations[:]
    current_st = st[:]
    temp_dir = output_path.parent
    round_num = 0

    while len(current) > 1:
        next_round = []
        next_dur = []
        next_st = []
        round_num += 1

        for i in range(0, len(current), 2):
            if i + 1 >= len(current):
                next_round.append(current[i])
                next_dur.append(current_dur[i])
                next_st.append(current_st[i])
                continue

            a, b = current[i], current[i + 1]
            da, db = current_dur[i], current_dur[i + 1]
            out = temp_dir / f"xfade_r{round_num}_g{i//2:02d}.mp4"
            offset = da - transition_dur
            if offset < 0:
                offset = 0

            trans = XFADE_MAP.get((current_st[i], current_st[i + 1]), "fade")
            fg = (
                f"[0:v][1:v]xfade=transition={trans}"
                f":duration={transition_dur}:offset={offset:.2f}[vout];"
                f"[0:a][1:a]acrossfade=d={transition_dur}[aout]"
            )
            cmd = [
                "ffmpeg", "-y", "-i", a, "-i", b,
                "-filter_complex", fg,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                str(out),
            ]
            _run_ffmpeg(cmd, f"Xfade {i}+{i+1}")

            next_round.append(str(out))
            next_dur.append(da + db - transition_dur)
            next_st.append(current_st[i])

        current = next_round
        current_dur = next_dur
        current_st = next_st

    if current[0] != str(output_path):
        shutil.move(current[0], output_path)


def _run_ffmpeg(cmd: List[str], step_name: str = "FFmpeg"):
    """Run FFmpeg and raise on error."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        msg = e.stderr[-500:] if e.stderr else str(e)
        raise RuntimeError(f"{step_name} hatası: {msg}") from e
    except FileNotFoundError:
        raise RuntimeError("FFmpeg bulunamadı (PATH'de değil veya yüklü değil)")


def _escape_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:")


def convert_to_vertical(input_path: str, output_path: str) -> str:
    if not Path(input_path).exists():
        raise FileNotFoundError(f"Giriş dosyası bulunamadı: {input_path}")
    Path(output_path).parent.mkdir(exist_ok=True, parents=True)
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-y", output_path,
    ]
    _run_ffmpeg(cmd, "Dikey format dönüşümü")
    return output_path
