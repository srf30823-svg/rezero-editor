"""FFmpeg render engine: crop pipeline, Ken Burns x/y center, 16 geçiş, hwaccel, face-crop."""
import subprocess
import json
import tempfile
import shutil
import os
from pathlib import Path
from typing import Optional, Union, List

from audio.music_selector import select_music, analyze_clips_mood, get_music_dir
from audio.voice_ducking import apply_ducking
from audio.sfx_engine import apply_sfx, get_sfx_preset
from knowledge.owl_director import direct_edit_owl
from rich.console import Console

console = Console()

TRANSITION_DURATION = 0.35
FPS = 30
WIDTH = 480
HEIGHT = 854

CINEMATIC_XFADE = {
    ("action", "action"): "wipeleft",
    ("action", "dialogue"): "fade",
    ("action", "emotional"): "fade",
    ("action", "atmospheric"): "smoothleft",
    ("dialogue", "action"): "wipeleft",
    ("dialogue", "dialogue"): "dissolve",
    ("dialogue", "emotional"): "smoothleft",
    ("dialogue", "atmospheric"): "fade",
    ("emotional", "action"): "wipeup",
    ("emotional", "dialogue"): "fade",
    ("emotional", "emotional"): "dissolve",
    ("emotional", "atmospheric"): "fade",
    ("atmospheric", "action"): "fade",
    ("atmospheric", "dialogue"): "dissolve",
    ("atmospheric", "emotional"): "fade",
    ("atmospheric", "atmospheric"): "dissolve",
}

COLOR_GRADE_MAP = {
    "action": "eq=saturation=1.4:contrast=1.15:brightness=0.03",
    "emotional": "eq=saturation=1.1:contrast=1.0:brightness=0.08:colorbalance=rh=0.03",
    "dialogue": "eq=saturation=1.0:contrast=1.0:brightness=0.0",
    "atmospheric": "eq=saturation=0.8:contrast=1.2:brightness=-0.05",
}


def _detect_hwaccel() -> List[str]:
    """Auto-detect best available hardware acceleration (verified working)."""
    try:
        r = subprocess.run(["ffmpeg", "-hwaccels"], capture_output=True, text=True, timeout=5)
        available = r.stdout.lower()
        for accel in ["cuda", "vaapi", "videotoolbox", "d3d12va"]:
            if accel in available:
                try:
                    test = subprocess.run(
                        ["ffmpeg", "-hwaccel", accel, "-f", "lavfi", "-i", "color=c=red:s=32x32:d=0.1",
                         "-f", "null", "-", "-y"],
                        capture_output=True, timeout=10
                    )
                    if test.returncode == 0:
                        opts = ["-hwaccel", accel]
                        if accel == "cuda":
                            opts.append("-hwaccel_output_format")
                            opts.append("cuda")
                        return opts
                except Exception:
                    continue
    except Exception:
        pass
    return []


def render_shorts(timeline: Union[dict, str], output_path: str,
                  music_path: Optional[str] = None,
                  subtitle_path: Optional[str] = None,
                  preserve_dialogue: bool = True,
                  use_llm: bool = True,
                  beat_times: Optional[List[float]] = None,
                  threads: int = 2,
                  hwaccel: bool = True) -> str:
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

    hwaccel_opts = _detect_hwaccel() if hwaccel else []
    if hwaccel_opts:
        console.print(f"[green]✓ HW ivme {hwaccel_opts[1]} kullanılıyor[/green]")

    output_dir = Path(output_path).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(exist_ok=True, parents=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="rezero_render_"))

    try:
        clip_paths = []
        durations = []
        scene_types = []
        for i, clip in enumerate(clips):
            p, dur = _render_clip(clip, i, temp_dir, hwaccel_opts, threads)
            preset = get_sfx_preset(clip)
            if preset.get("filter"):
                sfx_path = str(temp_dir / f"clip_{i:04d}_sfx.mp4")
                p = apply_sfx(p, None, clip, sfx_path)
                console.print(f"  [dim]SFX {i}: {preset['description']}[/dim]")
            clip_paths.append(p)
            durations.append(dur)
            scene_types.append(clip.get("scene_type", "dialogue"))

        if len(clip_paths) == 1:
            merged = temp_dir / "merged.mp4"
            shutil.copy(clip_paths[0], merged)
        else:
            merged = temp_dir / "merged.mp4"
            _concat_xfade(clip_paths, durations, merged, scene_types=scene_types, threads=threads)

        current = merged

        if subtitle_path:
            sp = Path(subtitle_path)
            if not sp.exists():
                console.print(f"[yellow]⚠ Altyazı dosyası bulunamadı: {subtitle_path}[/yellow]")
                subtitle_path = None
            else:
                subtitled = temp_dir / "subtitled.mp4"
                sub_cmd = [
                    "ffmpeg", "-i", str(current),
                    "-vf", f"subtitles={_escape_path(str(sp))}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "copy",
                    "-preset", "fast", "-crf", "23",
                    "-threads", str(threads),
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
                        dialogue_volume=3.0,
                        music_volume_normal=0.5,
                        music_volume_ducked=0.1,
                    )
                except RuntimeError as e:
                    console.print(f"[yellow]⚠ Ducking başarısız, basit karışıma dönülüyor: {e}[/yellow]")
                    preserve_dialogue = False
            if not preserve_dialogue:
                audio_cmd = [
                    "ffmpeg", "-i", str(current), "-i", music_path,
                    "-filter_complex",
                    "[0:a]volume=3.0[v];[1:a]volume=0.35[m];[v][m]amix=inputs=2:duration=first[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac",
                    "-threads", str(threads),
                    "-y", str(mixed),
                ]
                _run_ffmpeg(audio_cmd, "Ses karıştırma")
            current = mixed

        shutil.move(str(current), output_path)

    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

    return output_path


def _render_clip(clip: dict, index: int, temp_dir: Path,
                 hwaccel_opts: Optional[List[str]] = None, threads: int = 2) -> tuple:
    source = clip.get("source", "")
    if not source or not Path(source).exists():
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {source}")

    start = float(clip.get("start_time", 0.0))
    duration = float(clip.get("actual_duration", clip.get("duration", 3.0)))
    if duration <= 0:
        raise ValueError(f"Geçersiz süre: {duration}")

    scene_type = clip.get("scene_type", "dialogue")
    face_data = clip.get("faces", [])
    has_faces = clip.get("has_faces", False) and len(face_data) > 0
    output_path = str(temp_dir / f"clip_{index:04d}.mp4")

    hwaccel_opts = hwaccel_opts or []

    filters = []

    # Face-aware crop: center on detected face if available
    if has_faces:
        face = face_data[0]
        cx = face["x"] + face["w"] // 2
        cy = face["y"] + face["h"] // 2
        crop_w, crop_h = 480, 854
        filters.append(
            f"crop={crop_w}:{crop_h}:{cx - crop_w//2}:{cy - crop_h//2}"
        )
    else:
        # Smart crop: take center 480x854 from source maintaining aspect ratio
        filters.append(
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}"
        )

    # Ken Burns zoom with center tracking — dramatic speed for visible animation
    nframes = int(duration * FPS)
    if nframes < 2:
        nframes = 2
    speed = 0.008  # was 0.0006 — 13x faster for visible zoom
    if index % 2 == 0:
        zoom_end = 1.0 + speed * nframes
        zoom_expr = f"if(eq(on,1),1.0,zoom+{speed})"
    else:
        zoom_end = 1.15 - speed * nframes
        if zoom_end < 1.0:
            zoom_expr = f"if(eq(on,1),1.15,zoom-{speed})"
        else:
            zoom_expr = f"if(eq(on,1),1.15,zoom-{speed})"

    x_expr = "iw/2 - (iw/zoom)/2"
    y_expr = "ih/2 - (ih/zoom)/2"
    filters.append(
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={nframes}:fps={FPS}:s={WIDTH}x{HEIGHT}"
    )

    # Inline effects based on scene type
    intensity = clip.get("intensity", 5)
    if scene_type == "action" and intensity >= 6:
        filters.append("drawbox=c=white:t=fill")
    if scene_type == "action" and intensity >= 8:
        filters.append("crop=iw-2:ih-2:1:1,scale=480:854:flags=neighbor")

    # Color grading
    grade = COLOR_GRADE_MAP.get(scene_type)
    if grade:
        filters.append(grade)

    vf = ",".join(filters)

    cmd = ["ffmpeg", "-y"]
    cmd.extend(hwaccel_opts)
    cmd.extend(["-ss", str(start), "-i", source])
    cmd.extend(["-t", str(duration), "-vf", vf])
    cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "26"])
    cmd.extend(["-threads", str(threads)])
    cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ac", "2"])
    cmd.append(output_path)

    _run_ffmpeg(cmd, f"Klip {index} render")

    return output_path, duration


def _concat_xfade(clip_paths: List[str], durations: List[float],
                  output_path: Path, transition_dur: float = TRANSITION_DURATION,
                  scene_types: Optional[List[str]] = None, threads: int = 2):
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

            trans = CINEMATIC_XFADE.get((current_st[i], current_st[i + 1]), "fade")
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
                "-threads", str(threads),
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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        msg = e.stderr[-500:] if e.stderr else str(e)
        raise RuntimeError(f"{step_name} hatası: {msg}") from e
    except FileNotFoundError:
        raise RuntimeError("FFmpeg bulunamadı (PATH'de değil veya yüklü değil)")


def _escape_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:")
