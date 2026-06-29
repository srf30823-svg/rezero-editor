"""OWL Vision-Language Model ile çok boyutlu sahne analizi.

Her sahne için duygusal vektör:
    {
        "scene_id": 42,
        "primary_type": "dialogue",
        "sub_type": "confrontation",
        "valence": -0.6,
        "arousal": 0.8,
        "narrative_role": "inciting",
        "audio_energy": 0.72,
        "visual_density": 0.65
    }

Optimizasyonlar:
- Batch: 10 sahne = 1 çağrı
- Cache: scene_id hash ile tekrar engelle
- Max 5 çağrı/video
"""
import os
import json
import hashlib
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import requests


# ─── OpenRouter OWL Konfigürasyon ───────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OWL_MODEL = "owl"  # veya "qwen/qwen2.5-vl-72b-instruct"

BATCH_SIZE = 10          # sahne/çağrı
MAX_CALLS_PER_VIDEO = 5  # güvenlik limiti
CACHE_DIR = Path(__file__).parent.parent / ".cache" / "owl_analysis"

# Sahne tipi ve narrative role kategorileri
VALID_PRIMARY_TYPES = {"action", "dialogue", "emotional", "atmospheric", "transition"}
VALID_SUB_TYPES = {
    "confrontation", "monologue", "battle", "chase", "revelation",
    "mourning", "celebration", "tension", "peace", "flashback",
    "dialogue_casual", "dialogue_intense", "transformation",
}
VALID_NARRATIVE_ROLES = {
    "hook", "setup", "inciting", "rising", "climax",
    "falling", "resolution", "end", "transition",
}


# ─── OWL API Çağrısı ────────────────────────────────────────────

def _call_owl(prompt: str, images_b64: List[str] = None) -> str:
    """OpenRouter OWL API'ye çağrı yap.

    Args:
        prompt: Metin promptu
        images_b64: Base64'e çevrilmiş JPEG görüntü listesi

    Returns:
        LLM yanıtı (JSON string)
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ayarlanmamış")

    content = []
    if images_b64:
        for img in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img}"},
            })
    content.append({"type": "text", "text": prompt})

    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OWL_MODEL,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 2000,
            "temperature": 0.3,  # deterministik çıktı
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ─── Görüntü Çıkarma ────────────────────────────────────────────

def _extract_keyframe(video_path: str, timestamp: float) -> Optional[str]:
    """Belirli zamanda keyframe çıkar ve base64 döndür.

    Returns:
        Base64 JPEG string veya None
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-f", "image2",
        tmp_path,
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=15)
    if r.returncode != 0:
        return None

    with open(tmp_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    os.unlink(tmp_path)
    return data


def _extract_three_keyframes(video_path: str, start: float, end: float) -> List[str]:
    """Sahnenin başlangıç, orta ve bitişinden 3 kare çıkar."""
    mid = (start + end) / 2
    frames = []
    for t in [start + 0.5, mid, end - 0.5]:
        b64 = _extract_keyframe(video_path, max(0, t))
        if b64:
            frames.append(b64)
    return frames


# ─── Cache Yönetimi ─────────────────────────────────────────────

def _scene_cache_key(video_path: str, scene: dict) -> str:
    """Sahne için deterministik cache key üret."""
    data = f"{video_path}:{scene['scene_id']}:{scene['start']}:{scene['end']}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _load_cached_analysis(cache_key: str) -> Optional[dict]:
    """Cache'den analiz sonucu oku."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cached_analysis(cache_key: str, analysis: dict) -> None:
    """Analiz sonucunu cache'e kaydet."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)


# ─── Prompt Oluşturma ───────────────────────────────────────────

def _build_batch_prompt(scenes: List[dict], video_name: str) -> str:
    """OWL için batch analiz promptu oluştur.

    Her sahne için 3 kare (başlangıç/orta/bitiş) gönderilir.
    """
    prompt_parts = [
        "Analyze these video scenes and return a JSON array. For each scene, provide:",
        "",
        "{",
        '  "scene_id": <number>,',
        '  "primary_type": one of [action, dialogue, emotional, atmospheric, transition],',
        '  "sub_type": one of [confrontation, monologue, battle, chase, revelation, mourning, celebration, tension, peace, flashback, dialogue_casual, dialogue_intense, transformation],',
        '  "valence": <-1.0 to 1.0>,  // emotional positivity',
        '  "arousal": <0.0 to 1.0>,   // energy/intensity',
        '  "narrative_role": one of [hook, setup, inciting, rising, climax, falling, resolution, end, transition],',
        '  "audio_energy": <0.0 to 1.0>,   // from audio analysis',
        '  "visual_density": <0.0 to 1.0>  // visual complexity',
        "}",
        "",
        f"Video: {video_name}",
        f"Scenes to analyze: {len(scenes)}",
        "",
        "Guidelines:",
        "- valence < 0: negative emotions (sadness, anger, fear)",
        "- valence > 0: positive emotions (joy, hope, love)",
        "- arousal: low = calm/slow, high = intense/fast",
        "- narrative_role: story progression position",
        "- Return ONLY the JSON array, no markdown, no explanation.",
        "",
        "Scenes:",
    ]

    for s in scenes:
        prompt_parts.append(
            f"  Scene {s['scene_id']}: duration={s['duration']:.1f}s, "
            f"motion={s['motion_magnitude']:.1f}, audio_rms={s['audio_rms']:.4f}, "
            f"speech={'yes' if s['speech_detected'] else 'no'}"
        )

    return "\n".join(prompt_parts)


# ─── Yanıt Ayrıştırma ───────────────────────────────────────────

def _parse_owl_response(response: str, scene_ids: List[int]) -> List[dict]:
    """OWL yanıtını JSON olarak ayrıştır ve doğrula.

    Returns:
        Her sahne için analiz dict listesi
    """
    # JSON çıkarma (markdown kod bloğu olabilir)
    json_str = response
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_str = response.split("```")[1].split("```")[0].strip()

    try:
        analyses = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: satır satır dene
        analyses = []
        for line in response.split("\n"):
            line = line.strip()
            if line and line.startswith("{"):
                try:
                    analyses.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not isinstance(analyses, list):
        analyses = [analyses] if isinstance(analyses, dict) else []

    # Doğrula ve normalize et
    results = []
    for i, sid in enumerate(scene_ids):
        analysis = analyses[i] if i < len(analyses) else {}

        result = {
            "scene_id": sid,
            "primary_type": _validate_string(
                analysis.get("primary_type", "atmospheric"),
                VALID_PRIMARY_TYPES, "atmospheric",
            ),
            "sub_type": _validate_string(
                analysis.get("sub_type", "peace"),
                VALID_SUB_TYPES, "peace",
            ),
            "valence": _clamp_float(analysis.get("valence", 0.0), -1.0, 1.0),
            "arousal": _clamp_float(analysis.get("arousal", 0.5), 0.0, 1.0),
            "narrative_role": _validate_string(
                analysis.get("narrative_role", "transition"),
                VALID_NARRATIVE_ROLES, "transition",
            ),
            "audio_energy": _clamp_float(analysis.get("audio_energy", 0.5), 0.0, 1.0),
            "visual_density": _clamp_float(analysis.get("visual_density", 0.5), 0.0, 1.0),
        }
        results.append(result)

    return results


def _validate_string(value: str, valid_set: set, default: str) -> str:
    """Değerin geçerli kümede olup olmadığını kontrol et."""
    v = str(value).lower().strip()
    return v if v in valid_set else default


def _clamp_float(value, min_val: float, max_val: float) -> float:
    """Float değeri kısıtla."""
    try:
        f = float(value)
        return max(min_val, min(max_val, f))
    except (ValueError, TypeError):
        return (min_val + max_val) / 2


# ─── Ana Analiz Fonksiyonu ─────────────────────────────────────

def deep_analyze_video(
    video_path: str,
    scenes: List[dict],
    use_cache: bool = True,
    use_owl: bool = True,
) -> List[dict]:
    """Videonun tüm sahnelerini çok boyutlu olarak analiz et.

    Pipeline:
        1. Cache kontrolü (scene_id hash)
        2. Batch'leri oluştur (10 sahne/çğrı)
        3. Her batch için: 3 kare + metadata → OWL
        4. JSON array yanıtını ayrıştır
        5. Sonuçları birleştir ve cache'e kaydet

    Args:
        video_path: Video dosya yolu
        scenes: scanner çıktısı sahne listesi
        use_cache: Cache kullan
        use_owl: OWL API kullan (False = heuristic fallback)

    Returns:
        Her sahne için zenginleştirilmiş analiz dict listesi
    """
    video_path = str(video_path)
    video_name = Path(video_path).name

    print(f"[deep_analyzer] {len(scenes)} sahne analiz ediliyor...")

    enriched_scenes = []
    owl_call_count = 0

    # Batch'lere böl
    for batch_start in range(0, len(scenes), BATCH_SIZE):
        if owl_call_count >= MAX_CALLS_PER_VIDEO:
            print(f"[deep_analyzer] ⚠ Max {MAX_CALLS_PER_VIDEO} çağrı limitine ulaşıldı")
            break

        batch = scenes[batch_start:batch_start + BATCH_SIZE]
        batch_ids = [s["scene_id"] for s in batch]

        # Cache kontrolü
        if use_cache:
            cached_results = []
            all_cached = True
            for s in batch:
                cache_key = _scene_cache_key(video_path, s)
                cached = _load_cached_analysis(cache_key)
                if cached:
                    cached_results.append(cached)
                else:
                    all_cached = False
                    break

            if all_cached:
                print(f"[deep_analyzer] Cache hit: sahneler {batch_ids[0]}-{batch_ids[-1]}")
                enriched_scenes.extend(cached_results)
                continue

        # OWL çağrısı
        if use_owl and OPENROUTER_API_KEY:
            try:
                # 3 kare çıkar (ilk sahne için - batch representative)
                representative = batch[len(batch) // 2]
                frames = _extract_three_keyframes(
                    video_path,
                    representative["start"],
                    representative["end"],
                )

                prompt = _build_batch_prompt(batch, video_name)
                response = _call_owl(prompt, frames[:3])  # max 3 frame

                analyses = _parse_owl_response(response, batch_ids)
                owl_call_count += 1
                print(f"[deep_analyzer] OWL çağrı {owl_call_count}/{MAX_CALLS_PER_VIDEO}: "
                      f"sahneler {batch_ids[0]}-{batch_ids[-1]}")

            except Exception as e:
                print(f"[deep_analyzer] ⚠ OWL hatası: {e}, heuristic fallback kullanılıyor")
                analyses = _heuristic_analysis(batch)
        else:
            analyses = _heuristic_analysis(batch)

        # Ses enerjisini ekle (scanner'dan gelen değerleri normalize et)
        for i, s in enumerate(batch):
            if i < len(analyses):
                analyses[i]["audio_energy"] = _clamp_float(
                    s.get("audio_rms", 0.5) * 10, 0.0, 1.0
                )
                analyses[i]["visual_density"] = _clamp_float(
                    s.get("motion_magnitude", 50) / 200, 0.0, 1.0
                )

        # Cache'e kaydet
        if use_cache:
            for i, s in enumerate(batch):
                if i < len(analyses):
                    cache_key = _scene_cache_key(video_path, s)
                    _save_cached_analysis(cache_key, analyses[i])

        enriched_scenes.extend(analyses)

    print(f"[deep_analyzer] ✓ {len(enriched_scenes)} sahne zenginleştirildi "
          f"({owl_call_count} OWL çağrısı)")

    return enriched_scenes


def _heuristic_analysis(scenes: List[dict]) -> List[dict]:
    """OWL kapalıyken heuristic tabanlı analiz.

    motion_magnitude + audio_rms değerlerine göre tahmin.
    """
    results = []

    for s in scenes:
        motion = s.get("motion_magnitude", 50)
        audio_rms = s.get("audio_rms", 0.1)
        speech = s.get("speech_detected", False)

        # Tip belirleme
        if motion > 100:
            primary = "action"
            sub = "battle" if audio_rms > 0.2 else "chase"
        elif speech and audio_rms > 0.1:
            primary = "dialogue"
            sub = "dialogue_intense" if audio_rms > 0.3 else "dialogue_casual"
        elif motion < 20 and audio_rms < 0.05:
            primary = "atmospheric"
            sub = "peace"
        else:
            primary = "emotional"
            sub = "tension" if motion > 50 else "mourning"

        # Duygusal değerler
        valence = 0.0
        if primary == "atmospheric":
            valence = 0.1
        elif primary == "emotional":
            valence = -0.3
        elif primary == "dialogue":
            valence = -0.1 if sub == "dialogue_intense" else 0.2
        elif primary == "action":
            valence = -0.2

        arousal = min(1.0, motion / 150 + audio_rms * 2)

        # Narrative role (pozisyona göre)
        sid = s.get("scene_id", 0)
        if sid < 3:
            role = "hook"
        elif sid < 6:
            role = "setup"
        elif sid < 10:
            role = "rising"
        elif sid < 13:
            role = "climax"
        else:
            role = "resolution"

        results.append({
            "scene_id": s["scene_id"],
            "primary_type": primary,
            "sub_type": sub,
            "valence": round(valence, 2),
            "arousal": round(arousal, 2),
            "narrative_role": role,
            "audio_energy": round(min(1.0, audio_rms * 10), 2),
            "visual_density": round(min(1.0, motion / 200), 2),
        })

    return results


# ─── CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Kullanım: python deep_analyzer.py <video.mp4> <scenes.jsonl> [output.json]")
        sys.exit(1)

    video = sys.argv[1]
    scenes_file = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else "scenes_owl.json"

    # Sahneleri yükle
    from video.scanner import load_scenes
    scenes = load_scenes(scenes_file)

    # Analiz et
    analyses = deep_analyze_video(video, scenes)

    # Kaydet
    with open(output, "w", encoding="utf-8") as f:
        json.dump(analyses, f, ensure_ascii=False, indent=2)
    print(f"[deep_analyzer] ✓ Çıktı: {output}")
