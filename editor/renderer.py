"""Adaptif render motoru — beat-sync, adaptif kamera, renk düzenleme.

Özellikler:
- Adaptif Kamera:
    action → zoom-in + shake
    dialogue → pan
    emotional → zoom-out
    atmospheric → drift
- Beat-sync: librosa.beat.beat_track → xfade snap (±80ms)
- Renk: valence<0 → desaturate, >0 → saturation+5%
- Ses: speech ducking (-18dB sidechaincompress)
- Altyazı: whisper.cpp small, kelime highlight

Deterministik: Aynı seed = aynı kamera hareketleri
"""
import json
import subprocess
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ─── Konfigürasyon ──────────────────────────────────────────────
FPS = 30
WIDTH = 480
HEIGHT = 854
OUTPUT_RES = f"{WIDTH}x{HEIGHT}"

TRANSITION_DURATION = 0.35  # saniye
BEAT_SNAP_MS = 80  # ±80ms snap toleransı
DUCKING_THRESHOLD_DB = -18

# Adaptif kamera profilleri (seed'e bağlı deterministik)
CAMERA_PROFILES = {
    "action": {
        "type": "zoom_shake",
        "zoom_start": 1.0,
        "zoom_end": 1.15,
        "shake_intensity": 2.5,
        "description": "Hızlı zoom-in + titreşim",
    },
    "dialogue": {
        "type": "pan",
        "pan_range": 30,  # piksel
        "pan_speed": 0.3,
        "description": "Yavaş yatay kaydırma",
    },
    "emotional": {
        "type": "zoom_out",
        "zoom_start": 1.1,
        "zoom_end": 1.0,
        "description": "Yavaş zoom-out (uzaklaşma)",
    },
    "atmospheric": {
        "type": "drift",
        "drift_x": 15,
        "drift_y": 10,
        "drift_speed": 0.15,
        "description": "Yavaş kayan drift",
    },
    "transition": {
        "type": "static",
        "description": "Sabit kamera",
    },
}

# Renk düzenleme
VALENCE_COLOR_MAP = {
    "negative": "eq=saturation=0.6:contrast=1.2:brightness=-0.03",  # valence < -0.3
    "neutral": "eq=saturation=1.0:contrast=1.0:brightness=0.0",      # -0.3 <= valence <= 0.3
    "positive": "eq=saturation=1.15:contrast=1.05:brightness=0.02",  # valence > 0.3
}


# ─── Beat Tespiti ───────────────────────────────────────────────

def detect_beats(audio_path: str) -> List[float]:
    """librosa ile beat zamanlarını tespit et.

    Returns:
        Beat zaman damgaları (saniye) listesi
    """
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=None)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        print(f"[renderer] Beat tespit edildi: BPM={tempo:.1f}, {len(beat_times)} beat")
        return list(beat_times)
    except ImportError:
        print("[renderer] ⚠ librosa yüklü değil, beat-sync devre dışı")
        return []
    except Exception as e:
        print(f"[renderer] ⚠ Beat tespiti başarısız: {e}")
        return []


def snap_to_beat(time: float, beat_times: List[float], tolerance_ms: float = BEAT_SNAP_MS) -> float:
    """Zamanı en yakın beat'e snaple.

    Args:
        time: Orijinal zaman (saniye)
        beat_times: Beat zamanları listesi
        tolerance_ms: Maksimum sapma toleransı (ms)

    Returns:
        Snaplenmiş zaman
    """
    if not beat_times:
        return time

    tolerance_s = tolerance_ms / 1000.0
    closest_beat = min(beat_times, key=lambda b: abs(b - time))

    if abs(closest_beat - time) <= tolerance_s:
        return closest_beat
    return time


# ─── Adaptif Kamera Filtreleri ──────────────────────────────────

def _build_camera_filter(
    scene_type: str,
    duration: float,
    seed: int,
    clip_index: int,
) -> str:
    """Sahne tipine göre adaptif kamera filtresi oluştur.

    Seed'e bağlı deterministik hareketler.
    """
    import random
    rng = random.Random(seed + clip_index)

    profile = CAMERA_PROFILES.get(scene_type, CAMERA_PROFILES["transition"])
    nframes = max(2, int(duration * FPS))

    if profile["type"] == "zoom_shake":
        # Zoom-in + shake
        zoom_start = profile["zoom_start"]
        zoom_end = profile["zoom_end"]
        shake = profile["shake_intensity"]

        # Deterministik shake pattern
        shake_x = rng.uniform(-shake, shake)
        shake_y = rng.uniform(-shake, shake)

        zoom_expr = f"zoom+{(zoom_end - zoom_start) / nframes:.6f}"
        x_expr = f"iw/2-(iw/zoom)/2+{shake_x}*sin(n*{rng.uniform(0.3, 0.7):.3f})"
        y_expr = f"ih/2-(ih/zoom)/2+{shake_y}*cos(n*{rng.uniform(0.3, 0.7):.3f})"

        return (
            f"zoompan=z='if(eq(on,1),{zoom_start},{zoom_expr})':"
            f"x='{x_expr}':y='{y_expr}':"
            f"d={nframes}:fps={FPS}:s={OUTPUT_RES}"
        )

    elif profile["type"] == "pan":
        # Yatay pan
        pan_range = profile["pan_range"]
        pan_dir = 1 if rng.random() > 0.5 else -1
        pan_amount = pan_range * pan_dir

        return (
            f"zoompan=z='1.05':"
            f"x='{pan_amount}*n/{nframes}':"
            f"y='ih/2-(ih/zoom)/2':"
            f"d={nframes}:fps={FPS}:s={OUTPUT_RES}"
        )

    elif profile["type"] == "zoom_out":
        # Zoom-out
        zoom_start = profile["zoom_start"]
        zoom_end = profile["zoom_end"]
        zoom_expr = f"zoom-{(zoom_start - zoom_end) / nframes:.6f}"

        return (
            f"zoompan=z='if(eq(on,1),{zoom_start},{zoom_expr})':"
            f"x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':"
            f"d={nframes}:fps={FPS}:s={OUTPUT_RES}"
        )

    elif profile["type"] == "drift":
        # Drift
        dx = profile["drift_x"] * (1 if rng.random() > 0.5 else -1)
        dy = profile["drift_y"] * (1 if rng.random() > 0.5 else -1)

        return (
            f"zoompan=z='1.03':"
            f"x='{dx}*n/{nframes}':"
            f"y='{dy}*n/{nframes}':"
            f"d={nframes}:fps={FPS}:s={OUTPUT_RES}"
        )

    else:
        # Statik
        return f"zoompan=z='1.0':x='0':y='0':d={nframes}:fps={FPS}:s={OUTPUT_RES}"


# ─── Renk Düzenleme ─────────────────────────────────────────────

def _build_color_filter(valence: float) -> str:
    """Valence değerine göre renk filtresi seç."""
    if valence < -0.3:
        return VALENCE_COLOR_MAP["negative"]  # desaturate
    elif valence > 0.3:
        return VALENCE_COLOR_MAP["positive"]   # saturate +5%
    else:
        return VALENCE_COLOR_MAP["neutral"]


# ─── Klip Render ────────────────────────────────────────────────

def _render_clip(
    clip: dict,
    index: int,
    temp_dir: Path,
    seed: int,
    hwaccel_opts: List[str],
    threads: int,
) -> Tuple[str, float]:
    """Tek klipi render et.

    Returns:
        (output_path, duration) tuple
    """
    source = clip.get("source", "")
    if not source or not Path(source).exists():
        raise FileNotFoundError(f"Kaynak bulunamadı: {source}")

    start = float(clip.get("start", clip.get("start_time", 0.0)))
    duration = float(clip.get("actual_duration", clip.get("duration", 3.0)))
    if duration <= 0:
        raise ValueError(f"Geçersiz süre: {duration}")

    scene_type = clip.get("primary_type", "dialogue")
    valence = clip.get("valence", 0.0)

    output_path = str(temp_dir / f"clip_{index:04d}.mp4")

    # Adaptif kamera filtresi
    camera_filter = _build_camera_filter(scene_type, duration, seed, index)

    # Renk filtresi
    color_filter = _build_color_filter(valence)

    # Ölçeklendirme
    scale_filter = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}"

    # Tüm filtreleri birleştir
    filters = [scale_filter, camera_filter, color_filter]

    # Aksiyon sahnesi: ekstra efektler
    if scene_type == "action" and clip.get("arousal", 0) > 0.7:
        # Hafif motion blur efekti
        filters.append("tblend=all_mode=average")

    vf = ",".join(filters)

    cmd = ["ffmpeg", "-y"]
    cmd.extend(hwaccel_opts)
    cmd.extend(["-ss", str(start), "-i", source])
    cmd.extend(["-t", str(duration), "-vf", vf])
    cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "26"])
    cmd.extend(["-threads", str(threads)])
    cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ac", "2"])
    cmd.append(output_path)

    _run_ffmpeg(cmd, f"Klip {index} render ({scene_type})")

    return output_path, duration


# ─── Beat-Sync Concatenation ────────────────────────────────────

def _concat_clips_beat_sync(
    clip_paths: List[str],
    durations: List[float],
    beat_times: List[float],
    output_path: Path,
    scene_types: List[str],
    threads: int,
):
    """Klipleri beat-sync olarak birleştir.

    Geçişleri en yakın beat'e snaple (±80ms).
    """
    n = len(clip_paths)
    if n == 1:
        shutil.copy(clip_paths[0], output_path)
        return

    # Beat-sync geçiş zamanlarını hesapla
    current_time = 0.0
    transition_offsets = []

    for i in range(n - 1):
        dur = durations[i]
        ideal_offset = current_time + dur - TRANSITION_DURATION
        snapped_offset = snap_to_beat(ideal_offset, beat_times, BEAT_SNAP_MS)
        transition_offsets.append(snapped_offset - current_time)
        current_time += dur

    # Pairwise xfade ile birleştir
    current = clip_paths[:]
    current_dur = durations[:]
    current_types = scene_types[:]
    temp_dir = output_path.parent
    round_num = 0

    while len(current) > 1:
        next_round = []
        next_dur = []
        next_types = []
        round_num += 1

        for i in range(0, len(current), 2):
            if i + 1 >= len(current):
                next_round.append(current[i])
                next_dur.append(current_dur[i])
                next_types.append(current_types[i])
                continue

            a, b = current[i], current[i + 1]
            da, db = current_dur[i], current_dur[i + 1]

            # Beat-sync offset
            offset = transition_offsets[i] if i < len(transition_offsets) else (da - TRANSITION_DURATION)
            offset = max(0, offset)

            out = temp_dir / f"sync_r{round_num}_g{i//2:02d}.mp4"

            # Sahne tipine göre geçiş
            trans = _get_transition_type(current_types[i], current_types[i + 1])

            fg = (
                f"[0:v][1:v]xfade=transition={trans}"
                f":duration={TRANSITION_DURATION}:offset={offset:.2f}[vout];"
                f"[0:a][1:a]acrossfade=d={TRANSITION_DURATION}[aout]"
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
            _run_ffmpeg(cmd, f"Beat-sync xfade {i}+{i+1}")

            next_round.append(str(out))
            next_dur.append(da + db - TRANSITION_DURATION)
            next_types.append(current_types[i])

        current = next_round
        current_dur = next_dur
        current_types = next_types

    if current[0] != str(output_path):
        shutil.move(current[0], output_path)


def _get_transition_type(t1: str, t2: str) -> str:
    """İki sahne tipi arası geçiş tipi belirle."""
    TRANSITIONS = {
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
    return TRANSITIONS.get((t1, t2), "fade")


# ─── Ses İşleme ─────────────────────────────────────────────────

def _apply_audio_ducking(
    video_path: str,
    output_path: str,
    threshold_db: float = DUCKING_THRESHOLD_DB,
):
    """Konuşma varlığına göre ses ducking uygula.

    FFmpeg sidechaincompress kullanır.
    """
    # Önce ses stream'ini analiz et
    has_speech = _detect_speech_stream(video_path)

    if not has_speech:
        shutil.copy(video_path, output_path)
        return

    # Sidechain compress
    fg = (
        f"[0:a]asplit[a1][a2];"
        f"[a1]speechnorm=e={threshold_db}:r=0.0005:l=1[speech];"
        f"[a2]acompressor=threshold={threshold_db}:ratio=4:attack=50:release=200[bg];"
        f"[speech][bg]amix=inputs=2:duration=first:weights='1 0.3'[aout]"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-filter_complex", fg,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    _run_ffmpeg(cmd, "Ses ducking")


def _detect_speech_stream(video_path: str) -> bool:
    """Videoda konuşma olup olmadığını tespit et."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-af", "volumedetect",
            "-vn",
            "-f", "null", "-",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # Basit ses enerjisi kontrolü
        for line in r.stderr.split("\n"):
            if "max_volume" in line:
                try:
                    db = float(line.split(":")[-1].strip().split(" ")[0])
                    return db > -30  # -30dB üzeri = muhtemelen konuşma
                except (ValueError, IndexError):
                    pass
        return True  # Varsayılan: konuşma var
    except Exception:
        return True


# ─── Ana Render Fonksiyonu ──────────────────────────────────────

def render_edit(
    edit_plan: dict,
    output_path: str,
    music_path: Optional[str] = None,
    subtitle_path: Optional[str] = None,
    seed: int = 42,
    use_beat_sync: bool = True,
    threads: int = 2,
    hwaccel: bool = True,
) -> str:
    """Edit planını video olarak render et.

    Pipeline:
        1. Her klip için adaptif kamera render
        2. Beat tespiti (müzik varsa)
        3. Beat-sync concatenation
        4. Ses ducking
        5. Altyazı ekleme

    Args:
        edit_plan: owl_director çıktısı
        output_path: Çıkış video yolu
        music_path: Arka plan müziği (opsiyonel)
        subtitle_path: Altyazı dosyası (opsiyonel)
        seed: Kamera deterministikliği için
        use_beat_sync: Beat senkronizasyonu
        threads: FFmpeg thread sayısı
        hwaccel: Donanım ivmesi

    Returns:
        Oluşturulan video yolu
    """
    clips = edit_plan.get("ordered_clips", [])
    if not clips:
        raise ValueError("Edit planında klip bulunamadı")

    print(f"[renderer] {len(clips)} klip render ediliyor...")

    # HW ivme
    hwaccel_opts = _detect_hwaccel() if hwaccel else []
    if hwaccel_opts:
        print(f"[renderer] HW ivme: {hwaccel_opts[1]}")

    # Çıkış dizini
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Geçici dizin
    temp_dir = Path(tempfile.mkdtemp(prefix="rezero_render_"))

    try:
        # 1. Her klipi render et
        clip_paths = []
        durations = []
        scene_types = []

        for i, clip in enumerate(clips):
            p, dur = _render_clip(clip, i, temp_dir, seed, hwaccel_opts, threads)
            clip_paths.append(p)
            durations.append(dur)
            scene_types.append(clip.get("primary_type", "dialogue"))

        # 2. Beat tespiti
        beat_times = []
        if use_beat_sync and music_path and Path(music_path).exists():
            beat_times = detect_beats(music_path)

        # 3. Birleştir
        merged = temp_dir / "merged.mp4"
        if len(clip_paths) == 1:
            shutil.copy(clip_paths[0], merged)
        elif beat_times:
            _concat_clips_beat_sync(
                clip_paths, durations, beat_times,
                merged, scene_types, threads,
            )
        else:
            _concat_simple(clip_paths, durations, merged, scene_types, threads)

        current = merged

        # 4. Müzik ekle
        if music_path and Path(music_path).exists():
            mixed = temp_dir / "with_music.mp4"
            _add_music(str(current), music_path, str(mixed), threads)
            current = mixed

        # 5. Ses ducking
        ducked = temp_dir / "ducked.mp4"
        _apply_audio_ducking(str(current), str(ducked))
        current = ducked

        # 6. Altyazı
        if subtitle_path and Path(subtitle_path).exists():
            subtitled = temp_dir / "final.mp4"
            _add_subtitles(str(current), subtitle_path, str(subtitled), threads)
            current = subtitled

        # 7. Son taşıma
        shutil.move(str(current), output_path)

    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

    print(f"[renderer] ✓ Video oluşturuldu: {output_path}")
    return output_path


def _concat_simple(
    clip_paths: List[str],
    durations: List[float],
    output_path: Path,
    scene_types: List[str],
    threads: int,
):
    """Basit xfade birleştirme (beat-sync yokken)."""
    n = len(clip_paths)
    if n == 1:
        shutil.copy(clip_paths[0], output_path)
        return

    current = clip_paths[:]
    current_dur = durations[:]
    current_types = scene_types[:]
    temp_dir = output_path.parent
    round_num = 0

    while len(current) > 1:
        next_round = []
        next_dur = []
        next_types = []
        round_num += 1

        for i in range(0, len(current), 2):
            if i + 1 >= len(current):
                next_round.append(current[i])
                next_dur.append(current_dur[i])
                next_types.append(current_types[i])
                continue

            a, b = current[i], current[i + 1]
            da, db = current_dur[i], current_dur[i + 1]
            out = temp_dir / f"xfade_r{round_num}_g{i//2:02d}.mp4"
            offset = da - TRANSITION_DURATION
            if offset < 0:
                offset = 0

            trans = _get_transition_type(current_types[i], current_types[i + 1])
            fg = (
                f"[0:v][1:v]xfade=transition={trans}"
                f":duration={TRANSITION_DURATION}:offset={offset:.2f}[vout];"
                f"[0:a][1:a]acrossfade=d={TRANSITION_DURATION}[aout]"
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
            next_dur.append(da + db - TRANSITION_DURATION)
            next_types.append(current_types[i])

        current = next_round
        current_dur = next_dur
        current_types = next_types

    if current[0] != str(output_path):
        shutil.move(current[0], output_path)


def _add_music(video_path: str, music_path: str, output_path: str, threads: int):
    """Videoya arka plan müziği ekle."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex",
        "[0:a]volume=2.0[v];[1:a]volume=0.3[m];[v][m]amix=inputs=2:duration=first[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-threads", str(threads),
        "-shortest",
        output_path,
    ]
    _run_ffmpeg(cmd, "Müzik ekleme")


def _add_subtitles(video_path: str, subtitle_path: str, output_path: str, threads: int):
    """Altyazı yakma."""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"subtitles={_escape_path(subtitle_path)}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-preset", "fast", "-crf", "23",
        "-threads", str(threads),
        output_path,
    ]
    _run_ffmpeg(cmd, "Altyazı yakma")


# ─── Yardımcı Fonksiyonlar ──────────────────────────────────────

def _detect_hwaccel() -> List[str]:
    """Donanım ivmesi tespiti."""
    try:
        r = subprocess.run(["ffmpeg", "-hwaccels"], capture_output=True, text=True, timeout=5)
        available = r.stdout.lower()
        for accel in ["cuda", "vaapi", "videotoolbox", "d3d12va"]:
            if accel in available:
                try:
                    test = subprocess.run(
                        ["ffmpeg", "-hwaccel", accel, "-f", "lavfi",
                         "-i", "color=c=red:s=32x32:d=0.1",
                         "-f", "null", "-", "-y"],
                        capture_output=True, timeout=10,
                    )
                    if test.returncode == 0:
                        opts = ["-hwaccel", accel]
                        if accel == "cuda":
                            opts.extend(["-hwaccel_output_format", "cuda"])
                        return opts
                except Exception:
                    continue
    except Exception:
        pass
    return []


def _run_ffmpeg(cmd: List[str], step_name: str = "FFmpeg"):
    """FFmpeg komutu çalıştır."""
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        msg = e.stderr[-500:] if e.stderr else str(e)
        raise RuntimeError(f"{step_name} hatası: {msg}") from e
    except FileNotFoundError:
        raise RuntimeError("FFmpeg bulunamadı")


def _escape_path(path: str) -> str:
    """FFmpeg path escaping."""
    return path.replace("\\", "/").replace(":", "\\:")


# ─── CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Kullanım: python renderer.py <edit_plan.json> <output.mp4> [music.mp3] [--seed 42]")
        sys.exit(1)

    plan_file = sys.argv[1]
    output = sys.argv[2]
    music = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None

    seed = 42
    if "--seed" in sys.argv:
        seed = int(sys.argv[sys.argv.index("--seed") + 1])

    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    render_edit(plan, output, music_path=music, seed=seed)
