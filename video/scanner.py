"""PySceneDetect hibrit sahne tarayıcı — content + adaptive threshold.

Çıktı: scenes.jsonl — her satır bir sahne:
    {
        "scene_id": 0,
        "start": 0.00,
        "end": 5.23,
        "duration": 5.23,
        "motion_magnitude": 12.4,
        "audio_rms": 0.15,
        "speech_detected": false
    }

Özellikler:
- Content-aware detection (hist, luma diff)
- Adaptive threshold: düşük hareket → düşük threshold
- FFmpeg tabanlı hızlı ön-pass
- Her sahne için hareket + ses RMS hesaplama
"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


# ─── Konfigürasyon ──────────────────────────────────────────────
MIN_SCENE_DURATION = 1.5       # saniye
MAX_SCENE_DURATION = 15.0      # saniye
DEFAULT_THRESHOLD = 0.20       # content detect default
ADAPTIVE_LOW_MOTION = 0.12     # düşük hareketli sahneler için
ADAPTIVE_HIGH_MOTION = 0.30    # yüksek hareketli sahneler için
MOTION_WINDOW_SIZE = 5         # adaptive threshold pencere boyutu
FPS_SAMPLE = 5                 # hareket analizi için FPS


def _ffprobe_streams(video_path: str) -> dict:
    """FFprobe ile video stream bilgilerini al."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", video_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout else {}


def _extract_frame_motions(video_path: str, fps: int = FPS_SAMPLE) -> List[float]:
    """FFmpeg ile düşük FPS'te frame farklarını hesapla (hareket büyüklüğü).

    Returns:
        Her frame çifti arasındaki ortalama piksel farkı listesi.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Düşük FPS'te frame çıkar
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"fps={fps},scale=160:-1",
            "-pix_fmt", "gray",
            str(tmp / "frame_%06d.raw"),
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode != 0:
            return []

        frames = sorted(tmp.glob("frame_*.raw"))
        if len(frames) < 2:
            return []

        motions = []
        for i in range(len(frames) - 1):
            f1 = frames[i].read_bytes()
            f2 = frames[i + 1].read_bytes()
            min_len = min(len(f1), len(f2))
            if min_len == 0:
                motions.append(0.0)
                continue
            diff_sum = sum(abs(a - b) for a, b in zip(f1[:min_len], f2[:min_len]))
            avg_diff = diff_sum / min_len
            motions.append(avg_diff)

        return motions


def _detect_scenes_content(video_path: str, threshold: float = DEFAULT_THRESHOLD) -> List[float]:
    """FFmpeg scene filter ile içerik tabanlı sahne değişimi tespiti.

    Returns:
        Sahne değişim zaman damgaları (saniye), [0.0, ...].
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"select='gt(scene\\,\\{threshold})',showinfo",
        "-vsync", "0",
        "-an",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    timestamps = [0.0]
    for line in (r.stderr + r.stdout).split("\n"):
        if "pts_time:" in line:
            try:
                parts = line.split("pts_time:")[1].split()
                t = float(parts[0]) if parts else 0.0
                if t - timestamps[-1] >= MIN_SCENE_DURATION:
                    timestamps.append(t)
            except (ValueError, IndexError):
                pass

    # Video süresini al ve son sahneyi ekle
    duration = _get_duration(video_path)
    if timestamps[-1] < duration - 0.5:
        timestamps.append(duration)

    return sorted(timestamps)


def _get_duration(video_path: str) -> float:
    """Video süresi (saniye)."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", video_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = json.loads(r.stdout) if r.stdout else {}
    return float(data.get("format", {}).get("duration", 0))


def _compute_audio_rms(video_path: str, start: float, end: float) -> float:
    """Belirli bir zaman aralığının ses RMS değerini hesapla."""
    duration = end - start
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", video_path,
        "-af", "astats=measure_perchannel=none:measure_overall=rms_level",
        "-vn",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    for line in r.stderr.split("\n"):
        if "RMS level" in line and "dB" in line:
            try:
                db_str = line.split("dB")[0].split("=")[-1].strip()
                db = float(db_str)
                # dB'den lineer RMS'e çevir
                return 10 ** (db / 20)
            except (ValueError, IndexError):
                pass
    return 0.0


def _detect_speech(video_path: str, start: float, end: float) -> bool:
    """Basit speech detection: ses enerjisi + frekans analizi.

    Gerçek uygulamada VAD (Voice Activity Detection) kullanılabilir.
    Burada ses varlığı + RMS threshold ile basit tespit.
    """
    rms = _compute_audio_rms(video_path, start, end)
    # RMS > 0.05 ise muhtemelen konuşma var
    return rms > 0.05


def _compute_motion_for_segment(
    motions: List[float],
    start_time: float,
    end_time: float,
    fps: int = FPS_SAMPLE,
) -> float:
    """Belirli zaman aralığı için ortalama hareket büyüklüğü."""
    start_idx = int(start_time * fps)
    end_idx = int(end_time * fps)

    if start_idx >= len(motions) or end_idx > len(motions):
        return 0.0

    segment_motions = motions[start_idx:end_idx]
    if not segment_motions:
        return 0.0

    return sum(segment_motions) / len(segment_motions)


def scan_video(video_path: str, output_jsonl: Optional[str] = None) -> List[Dict]:
    """Videoyu tara ve sahne listesi döndür.

    Pipeline:
        1. FFmpeg content detect → raw sahne değişimleri
        2. Hareket analizi → adaptive threshold
        3. Çok kısa/uzun sahneleri birleştir/ayrıştır
        4. Her sahne için: motion, audio_rms, speech
        5. JSONL olarak kaydet

    Args:
        video_path: Giriş video dosyası
        output_jsonl: Çıktı JSONL yolu (None ise kaydetme)

    Returns:
        Sahne dict listesi
    """
    video_path = str(video_path)
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video bulunamadı: {video_path}")

    print(f"[scanner] Taranıyor: {Path(video_path).name}")

    # 1. Ham sahne tespiti
    raw_timestamps = _detect_scenes_content(video_path)
    print(f"[scanner] {len(raw_timestamps)} ham kesim noktası")

    # 2. Hareket analizi
    motions = _extract_frame_motions(video_path)
    avg_motion = sum(motions) / len(motions) if motions else 0.0

    # 3. Adaptive threshold uygula
    if avg_motion < 30:
        threshold = ADAPTIVE_LOW_MOTION
    elif avg_motion > 100:
        threshold = ADAPTIVE_HIGH_MOTION
    else:
        threshold = DEFAULT_THRESHOLD

    if threshold != DEFAULT_THRESHOLD:
        raw_timestamps = _detect_scenes_content(video_path, threshold)
        print(f"[scanner] Adaptive threshold={threshold:.2f}, {len(raw_timestamps)} kesim")

    # 4. Sahne oluştur
    duration = _get_duration(video_path)
    scenes = []
    scene_id = 0

    for i in range(len(raw_timestamps) - 1):
        start = raw_timestamps[i]
        end = raw_timestamps[i + 1]
        seg_duration = end - start

        # Çok kısa sahneleri atla (bir sonrakine ekle)
        if seg_duration < MIN_SCENE_DURATION:
            continue

        # Çok uzun sahneleri böl
        if seg_duration > MAX_SCENE_DURATION:
            sub_segments = _split_long_scene(start, end, MAX_SCENE_DURATION)
        else:
            sub_segments = [(start, end)]

        for sub_start, sub_end in sub_segments:
            motion_mag = _compute_motion_for_segment(motions, sub_start, sub_end)
            audio_rms = _compute_audio_rms(video_path, sub_start, sub_end)
            speech = _detect_speech(video_path, sub_start, sub_end)

            scene = {
                "scene_id": scene_id,
                "start": round(sub_start, 3),
                "end": round(sub_end, 3),
                "duration": round(sub_end - sub_start, 3),
                "motion_magnitude": round(motion_mag, 3),
                "audio_rms": round(audio_rms, 4),
                "speech_detected": speech,
            }
            scenes.append(scene)
            scene_id += 1

    print(f"[scanner] ✓ {len(scenes)} sahne oluşturuldu")

    # 5. JSONL kaydet
    if output_jsonl:
        output_path = Path(output_jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for scene in scenes:
                f.write(json.dumps(scene, ensure_ascii=False) + "\n")
        print(f"[scanner] ✓ scenes.jsonl kaydedildi: {output_path}")

    return scenes


def _split_long_scene(start: float, end: float, max_duration: float) -> List[tuple]:
    """Uzun sahneleri max_duration ile böler."""
    segments = []
    current = start
    while current < end:
        next_end = min(current + max_duration, end)
        segments.append((current, next_end))
        current = next_end
    return segments


def load_scenes(jsonl_path: str) -> List[Dict]:
    """scenes.jsonl dosyasını oku."""
    scenes = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                scenes.append(json.loads(line))
    return scenes


# ─── CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python scanner.py <video.mp4> [output.jsonl]")
        sys.exit(1)

    video = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "scenes.jsonl"
    scan_video(video, output)
