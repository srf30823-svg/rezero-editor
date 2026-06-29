"""OWL Director — Şablon kütüphanesi ve edit planlama.

Şablonlar:
    "hype":     ["hook(0-3s)", "rising×3", "climax", "end_cta"]
    "emotional":["atmospheric", "setup", "rising×2", "climax", "resolution"]
    "teaser":   ["hook", "climax_flash", "setup", "rising", "cliffhanger"]
    "recap":    ["montage×5", "climax", "end"]

OWL Çağrısı:
    Input:  Sahneler + şablon listesi
    Output: Şablon seçimi + sahne ataması
    NOT:    Sıralama LLM'e bırakılmaz (halüsinasyon önleme)

Çıktı: edit_plan.json
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import requests


# ─── OpenRouter Konfigürasyon ───────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OWL_MODEL = "owl"

CACHE_DIR = Path(__file__).parent.parent / ".cache" / "owl_director"


# ─── Şablon Kütüphanesi ─────────────────────────────────────────

TEMPLATES = {
    "hype": {
        "structure": ["hook(0-3s)", "rising", "rising", "rising", "climax", "end_cta"],
        "description": "Hızlı başlangıç, sürekli yükseliş, güçlü climax, CTA son",
        "best_for": "aksiyon, spor, hype içerik",
        "energy_curve": "low→high→very_high→max→drop",
        "typical_duration": 45,
    },
    "emotional": {
        "structure": ["atmospheric", "setup", "rising", "rising", "climax", "resolution"],
        "description": "Atmosferik başlangıç, karakter kurulumu, duygusal yükseliş, çözüm",
        "best_for": "drama, karakter gelişimi, duygusal hikayeler",
        "energy_curve": "low→medium→high→peak→warm",
        "typical_duration": 60,
    },
    "teaser": {
        "structure": ["hook", "climax_flash", "setup", "rising", "cliffhanger"],
        "description": "Güçlü kancalı başlangıç, climax flashforward, gizemli son",
        "best_for": "fragman, tanıtım, merak uyandıran içerik",
        "energy_curve": "high→medium→low→rising→cut",
        "typical_duration": 30,
    },
    "recap": {
        "structure": ["montage", "montage", "montage", "montage", "montage", "climax", "end"],
        "description": "Hızlı montaj, en önemli anlar, vurgulu climax",
        "best_for": "özet, highlight, en iyi anlar derlemesi",
        "energy_curve": "medium→high→medium→high→peak",
        "typical_duration": 55,
    },
}

# Narrative_role → şablon yapı elemanı eşleşmesi
ROLE_TO_STRUCTURE = {
    "hook": "hook(0-3s)",
    "setup": "setup",
    "inciting": "rising",
    "rising": "rising",
    "climax": "climax",
    "climax_flash": "climax_flash",
    "falling": "resolution",
    "resolution": "resolution",
    "end": "end_cta",
    "end_cta": "end_cta",
    "atmospheric": "atmospheric",
    "montage": "montage",
    "cliffhanger": "cliffhanger",
    "transition": None,
}


# ─── Cache ──────────────────────────────────────────────────────

def _plan_cache_key(clips: List[dict], template_hint: str) -> str:
    """Edit planı için cache key."""
    data = json.dumps(clips, sort_keys=True) + template_hint
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _load_cached_plan(cache_key: str) -> Optional[dict]:
    """Cache'den plan oku."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cached_plan(cache_key: str, plan: dict) -> None:
    """Planı cache'e kaydet."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


# ─── OWL Çağrısı ────────────────────────────────────────────────

def _call_owl(prompt: str) -> str:
    """OpenRouter OWL API'ye metin çağrısı."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ayarlanmamış")

    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OWL_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "temperature": 0.2,  # düşük sıcaklık = deterministik
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ─── Prompt Oluşturma ───────────────────────────────────────────

def _build_director_prompt(clips: List[dict], user_template: str = "") -> str:
    """OWL Director için prompt oluştur.

    NOT: Sıralama istemiyoruz, sadece şablon seçimi ve atama.
    """
    # Klip özeti
    clip_summaries = []
    for i, c in enumerate(clips):
        clip_summaries.append(
            f"[{i}] Scene {c.get('scene_id', '?')}: "
            f"type={c.get('primary_type', '?')}/{c.get('sub_type', '?')}, "
            f"valence={c.get('valence', 0):+.2f}, "
            f"arousal={c.get('arousal', 0):.2f}, "
            f"role={c.get('narrative_role', '?')}, "
            f"dur={c.get('actual_duration', c.get('duration', 0)):.1f}s"
        )

    # Şablon bilgileri
    template_infos = []
    for name, info in TEMPLATES.items():
        template_infos.append(
            f"  \"{name}\": {info['description']}\n"
            f"    structure: {info['structure']}\n"
            f"    best_for: {info['best_for']}"
        )

    prompt_parts = [
        "You are a video editing director. Select the best template and assign clips to structure slots.",
        "",
        "CRITICAL: Do NOT reorder clips. Keep their original order.",
        "Only assign existing clip indices to template slots.",
        "",
        "Available templates:",
        *template_infos,
        "",
        f"User preference: {user_template if user_template else 'auto-select'}",
        "",
        "Available clips (keep this order!):",
        *clip_summaries,
        "",
        'Return ONLY a JSON object with this exact format:',
        "{",
        '  "template": "template_name",',
        '  "assignments": [',
        '    {"slot": "hook", "clip_index": 0},',
        '    {"slot": "rising", "clip_index": 1},',
        '    ...',
        '  ],',
        '  "reasoning": "brief explanation"',
        "}",
        "",
        "Rules:",
        "- Every clip_index must be valid (0 to N-1)",
        "- Each clip can be used at most once",
        "- Not all clips need to be assigned",
        "- slot names must match the template structure",
    ]

    return "\n".join(prompt_parts)


# ─── Yanıt Ayrıştırma ───────────────────────────────────────────

def _parse_director_response(response: str, num_clips: int) -> dict:
    """OWL yanıtını ayrıştır ve doğrula."""
    # JSON çıkarma
    json_str = response
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_str = response.split("```")[1].split("```")[0].strip()

    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: en son {} içeriğini dene
        plan = {}
        try:
            start = response.rfind("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                plan = json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

    # Varsayılan değerler
    template = plan.get("template", "hype")
    if template not in TEMPLATES:
        template = "hype"

    assignments = plan.get("assignments", [])

    # Doğrula: geçerli clip_index'ler
    valid_assignments = []
    used_indices = set()

    for a in assignments:
        idx = a.get("clip_index", -1)
        if 0 <= idx < num_clips and idx not in used_indices:
            valid_assignments.append({
                "slot": a.get("slot", "montage"),
                "clip_index": idx,
            })
            used_indices.add(idx)

    # Eksik slotları doldur (fallback)
    structure = TEMPLATES[template]["structure"]
    existing_slots = {a["slot"] for a in valid_assignments}

    for slot in structure:
        if slot not in existing_slots:
            # Kullanılmamış ilk clip'i ata
            for i in range(num_clips):
                if i not in used_indices:
                    valid_assignments.append({"slot": slot, "clip_index": i})
                    used_indices.add(i)
                    break

    return {
        "template": template,
        "assignments": valid_assignments,
        "reasoning": plan.get("reasoning", "Auto-generated plan"),
        "structure": structure,
    }


# ─── Edit Planı Oluşturma ───────────────────────────────────────

def create_edit_plan(
    clips: List[dict],
    template: str = "",
    use_owl: bool = True,
    use_cache: bool = True,
) -> dict:
    """Edit planı oluştur.

    Pipeline:
        1. Cache kontrolü
        2. OWL çağrısı: şablon seç + atama (1 çağrı)
        3. Sıralama: narrative_role bazlı (LLM değil!)
        4. Planı doğrula ve kaydet

    Args:
        clips: selector çıktısı (seçilmiş klipler)
        template: Tercih edilen şablon (boş = auto)
        use_owl: OWL kullan
        use_cache: Cache kullan

    Returns:
        edit_plan dict:
        {
            "template": "hype",
            "structure": [...],
            "ordered_clips": [...],
            "transitions": [...],
            "timing": [...],
            "reasoning": "..."
        }
    """
    if not clips:
        return {"template": "hype", "ordered_clips": [], "reasoning": "No clips"}

    # Cache kontrolü
    cache_key = _plan_cache_key(clips, template)
    if use_cache:
        cached = _load_cached_plan(cache_key)
        if cached:
            print(f"[owl_director] Cache hit")
            return cached

    # OWL çağrısı (1 çağrı = son çağrı)
    if use_owl and OPENROUTER_API_KEY:
        try:
            prompt = _build_director_prompt(clips, template)
            response = _call_owl(prompt)
            owl_plan = _parse_director_response(response, len(clips))
            print(f"[owl_director] OWL: template={owl_plan['template']}, "
                  f"{len(owl_plan['assignments'])} atama")
        except Exception as e:
            print(f"[owl_director] ⚠ OWL hatası: {e}, fallback")
            owl_plan = _fallback_plan(clips, template)
    else:
        owl_plan = _fallback_plan(clips, template)

    # Sıralama: narrative_role bazlı (HALÜSİNASYON ÖNLEME)
    ordered_clips = _role_based_sort(clips, owl_plan)

    # Geçişleri belirle
    transitions = _determine_transitions(ordered_clips)

    # Zamanlamayı hesapla
    timing = _compute_timing(ordered_clips)

    edit_plan = {
        "template": owl_plan["template"],
        "structure": owl_plan.get("structure", TEMPLATES.get(owl_plan["template"], {}).get("structure", [])),
        "ordered_clips": ordered_clips,
        "transitions": transitions,
        "timing": timing,
        "reasoning": owl_plan.get("reasoning", ""),
    }

    # Cache'e kaydet
    if use_cache:
        _save_cached_plan(cache_key, edit_plan)

    return edit_plan


def _fallback_plan(clips: List[dict], preferred_template: str) -> dict:
    """OWL kapalıyken kural tabanlı plan."""
    # Template seçimi
    if preferred_template in TEMPLATES:
        template = preferred_template
    else:
        # Otomatik: clip karakteristiğine göre
        avg_arousal = sum(c.get("arousal", 0.5) for c in clips) / len(clips)
        avg_valence = sum(c.get("valence", 0) for c in clips) / len(clips)

        if avg_arousal > 0.7:
            template = "hype"
        elif avg_valence < -0.3:
            template = "emotional"
        elif avg_arousal > 0.5:
            template = "recap"
        else:
            template = "teaser"

    structure = TEMPLATES[template]["structure"]

    # Tüm clipleri sırayla ata
    assignments = []
    for i, slot in enumerate(structure):
        if i < len(clips):
            assignments.append({"slot": slot, "clip_index": i})

    return {
        "template": template,
        "assignments": assignments,
        "structure": structure,
        "reasoning": f"Fallback: {template} selected (auto-detect)",
    }


def _role_based_sort(clips: List[dict], owl_plan: dict) -> List[dict]:
    """Narrative role bazlı deterministik sıralama.

    OWL atamalarını narrative_role sıralamasına göre düzenler.
    LLM sıralama yapmaz — halüsinasyon önleme.
    """
    assignments = owl_plan.get("assignments", [])
    if not assignments:
        return clips

    # Role öncelik sırası (hikaye akışı)
    role_order = {
        "hook": 0, "hook(0-3s)": 0,
        "atmospheric": 1,
        "setup": 2,
        "montage": 3,
        "inciting": 4,
        "rising": 5,
        "climax_flash": 6,
        "climax": 7,
        "falling": 8,
        "resolution": 9,
        "end": 10, "end_cta": 10,
        "cliffhanger": 11,
    }

    # Atamaları sırala
    sorted_assignments = sorted(
        assignments,
        key=lambda a: role_order.get(a["slot"], 99),
    )

    # Clipleri bu sırayla düzenle
    ordered = []
    for a in sorted_assignments:
        idx = a["clip_index"]
        if 0 <= idx < len(clips):
            clip = dict(clips[idx])
            clip["assigned_slot"] = a["slot"]
            ordered.append(clip)

    # Kullanılmamış clipleri sona ekle
    used_indices = {a["clip_index"] for a in assignments}
    for i, clip in enumerate(clips):
        if i not in used_indices:
            c = dict(clip)
            c["assigned_slot"] = "montage"
            ordered.append(c)

    return ordered


def _determine_transitions(clips: List[dict]) -> List[str]:
    """Sahne tiplerine göre geçiş tipi belirle."""
    if len(clips) < 2:
        return []

    TRANSITION_MAP = {
        ("action", "action"): "hard_cut",
        ("action", "dialogue"): "fade",
        ("action", "emotional"): "dissolve",
        ("action", "atmospheric"): "wipe",
        ("dialogue", "action"): "cut",
        ("dialogue", "dialogue"): "dissolve",
        ("dialogue", "emotional"): "fade",
        ("dialogue", "atmospheric"): "fade",
        ("emotional", "action"): "cut",
        ("emotional", "dialogue"): "dissolve",
        ("emotional", "emotional"): "dissolve",
        ("emotional", "atmospheric"): "fade",
        ("atmospheric", "action"): "wipe",
        ("atmospheric", "dialogue"): "fade",
        ("atmospheric", "emotional"): "fade",
        ("atmospheric", "atmospheric"): "dissolve",
    }

    transitions = []
    for i in range(len(clips) - 1):
        t1 = clips[i].get("primary_type", "atmospheric")
        t2 = clips[i + 1].get("primary_type", "atmospheric")
        trans = TRANSITION_MAP.get((t1, t2), "cut")
        transitions.append(trans)

    return transitions


def _compute_timing(clips: List[dict]) -> List[dict]:
    """Her klip için başlangıç/bitiş zamanlarını hesapla."""
    timing = []
    current_time = 0.0

    for clip in clips:
        dur = clip.get("actual_duration", clip.get("duration", 3.0))
        timing.append({
            "start": round(current_time, 2),
            "end": round(current_time + dur, 2),
            "duration": round(dur, 2),
        })
        current_time += dur

    return timing


# ─── Yardımcı Fonksiyonlar ──────────────────────────────────────

def get_template_info(template_name: str) -> dict:
    """Şablon bilgisi al."""
    return TEMPLATES.get(template_name, {})


def list_templates() -> List[str]:
    """Mevcut şablonları listele."""
    return list(TEMPLATES.keys())


# ─── CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python owl_director.py <selected_clips.json> [--template hype]")
        sys.exit(1)

    clips_file = sys.argv[1]
    template = ""
    if "--template" in sys.argv:
        template = sys.argv[sys.argv.index("--template") + 1]

    with open(clips_file, "r", encoding="utf-8") as f:
        clips = json.load(f)

    plan = create_edit_plan(clips, template=template)

    output = "edit_plan.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print(f"\n[owl_director] Plan oluşturuldu: {output}")
    print(f"  Template: {plan['template']}")
    print(f"  Clips: {len(plan['ordered_clips'])}")
    print(f"  Reasoning: {plan['reasoning']}")
