"""Deterministik klip seçici — seed-bazlı, şablon destekli.

Özellikler:
- select_clips(target_duration, seed, template)
- random.seed(seed) → deterministik çeşitlilik
- Valence zigzag kısıtı (monoton değil)
- Arousal rampası: son 30s %70+
- _pick_arc_aware(): narrative_role iskelet + boşluk doldur
- Her tipten min 1, max 3

Şablonlar (owl_director.py'den gelir):
- "hype": hızlı, yoğun, climax odaklı
- "emotional": duygusal derinlik, karakter odaklı
- "teaser": gizem, spoiler'sız
- "recap": hızlı montaj, en önemli anlar
"""
import random
import json
from typing import Dict, List, Optional, Tuple


# ─── Şablon Konfigürasyonları ───────────────────────────────────

TEMPLATE_CONFIGS = {
    "hype": {
        "description": "Hızlı, yoğun, climax odaklı edit",
        "preferred_types": ["action", "action", "dialogue", "emotional"],
        "arousal_min": 0.6,
        "valence_range": (-0.8, 0.5),
        "narrative_weight": {
            "hook": 3, "setup": 1, "inciting": 2, "rising": 3,
            "climax": 4, "falling": 0, "resolution": 0, "end": 1,
        },
        "clip_count_target": 8,
    },
    "emotional": {
        "description": "Duygusal derinlik, karakter odaklı",
        "preferred_types": ["emotional", "dialogue", "dialogue", "atmospheric"],
        "arousal_min": 0.2,
        "valence_range": (-1.0, 0.8),
        "narrative_weight": {
            "hook": 1, "setup": 3, "inciting": 3, "rising": 2,
            "climax": 2, "falling": 3, "resolution": 3, "end": 2,
        },
        "clip_count_target": 6,
    },
    "teaser": {
        "description": "Gizem, spoiler'sız, merak uyandıran",
        "preferred_types": ["atmospheric", "dialogue", "action", "emotional"],
        "arousal_min": 0.3,
        "valence_range": (-0.5, 0.3),
        "narrative_weight": {
            "hook": 4, "setup": 3, "inciting": 2, "rising": 1,
            "climax": 0, "falling": 0, "resolution": 0, "end": 2,
        },
        "clip_count_target": 5,
    },
    "recap": {
        "description": "Hızlı montaj, en önemli anlar",
        "preferred_types": ["action", "action", "action", "emotional"],
        "arousal_min": 0.5,
        "valence_range": (-0.6, 0.6),
        "narrative_weight": {
            "hook": 2, "setup": 1, "inciting": 2, "rising": 3,
            "climax": 4, "falling": 1, "resolution": 1, "end": 1,
        },
        "clip_count_target": 10,
    },
}

# Tip limitleri
MIN_PER_TYPE = 1
MAX_PER_TYPE = 3

# Arousal rampası
FINAL_30S_AROUSAL_RATIO = 0.70  # son 30sn'nin %70'i yüksek arousal
HIGH_AROUSAL_THRESHOLD = 0.6

# Valence zigzag
VALENCE_ZIGZAG_MIN = 0.3  # ardışık sahneler arası min fark


# ─── Ana Seçim Fonksiyonu ───────────────────────────────────────

def select_clips(
    scenes: List[dict],
    target_duration: float = 59.0,
    seed: int = 42,
    template: str = "hype",
    min_clip_duration: float = 1.5,
    max_clip_duration: float = 8.0,
) -> List[dict]:
    """Deterministik klip seçimi.

    Algoritma:
        1. Seed ayarla (deterministiklik)
        2. Şablon konfigürasyonunu yükle
        3. Narrative iskelet oluştur (hook→setup→...)
        4. İskeleti sahnelerle doldur
        5. Valence zigzag kontrolü
        6. Arousal rampası kontrolü (son 30s)
        7. Süre kısıtını uygula

    Args:
        scenes: deep_analyzer çıktısı (zenginleştirilmiş sahneler)
        target_duration: Hedef toplam süre (saniye)
        seed: Deterministiklik için rastgele tohum
        template: Şablon adı (hype/emotional/teaser/recap)
        min_clip_duration: Minimum klip süresi
        max_clip_duration: Maksimum klip süresi

    Returns:
        Seçilmiş ve sıralanmış klip listesi
    """
    # Seed ayarla
    rng = random.Random(seed)

    # Şablon yükle
    config = TEMPLATE_CONFIGS.get(template, TEMPLATE_CONFIGS["hype"])

    if not scenes:
        return []

    # Geçerli sahneleri filtrele
    valid_scenes = [
        s for s in scenes
        if min_clip_duration <= s.get("duration", 0) <= max_clip_duration
    ]
    if not valid_scenes:
        valid_scenes = [s for s in scenes if s.get("duration", 0) >= 1.0]
    if not valid_scenes:
        return []

    # Narrative iskelet oluştur
    skeleton = _build_narrative_skeleton(config, valid_scenes, rng)

    # İskeleti doldur
    selected = _fill_skeleton(skeleton, valid_scenes, config, rng)

    # Valence zigzag uygula
    selected = _apply_valence_zigzag(selected, rng)

    # Arousal rampası uygula
    selected = _apply_arousal_ramp(selected, target_duration, rng)

    # Süre kısıtını uygula
    selected = _apply_duration_constraint(selected, target_duration)

    # Sırala
    selected.sort(key=lambda x: x.get("start", 0))

    print(f"[selector] {len(selected)} klip seçildi (seed={seed}, template={template})")
    return selected


# ─── Narrative İskelet ──────────────────────────────────────────

def _build_narrative_skeleton(
    config: dict,
    scenes: List[dict],
    rng: random.Random,
) -> List[str]:
    """Şablona göre narrative_role sıralaması oluştur.

    Returns:
        narrative_role string listesi (iskelet)
    """
    weights = config["narrative_weight"]

    # Ağırlıklı seçim ile iskelet oluştur
    available_roles = [r for r, w in weights.items() if w > 0]
    if not available_roles:
        available_roles = ["hook", "rising", "climax", "end"]

    clip_target = config.get("clip_count_target", 8)

    # İlk iskelet: ağırlıklı seçim
    skeleton = []
    for _ in range(clip_target):
        role_weights = [weights.get(r, 1) for r in available_roles]
        total = sum(role_weights)
        if total == 0:
            role = rng.choice(available_roles)
        else:
            pick = rng.uniform(0, total)
            cumsum = 0
            for role, w in zip(available_roles, role_weights):
                cumsum += w
                if pick <= cumsum:
                    skeleton.append(role)
                    break
            else:
                skeleton.append(available_roles[-1])

    # İlk eleman her zaman hook olmalı
    if skeleton and skeleton[0] != "hook":
        # Hook var mı kontrol et
        if "hook" in skeleton:
            hook_idx = skeleton.index("hook")
            skeleton[0], skeleton[hook_idx] = skeleton[hook_idx], skeleton[0]
        else:
            skeleton[0] = "hook"

    return skeleton


# ─── İskelet Doldurma ───────────────────────────────────────────

def _fill_skeleton(
    skeleton: List[str],
    scenes: List[dict],
    config: dict,
    rng: random.Random,
) -> List[dict]:
    """Narrative iskeleti gerçek sahnelerle doldur.

    Her narrative_role için en uygun sahneyi seç.
    """
    selected = []
    used_scene_ids = set()

    # Tip sayaçları
    type_counts: Dict[str, int] = {}

    for role in skeleton:
        # Bu role için en uygun sahneleri bul
        candidates = _score_scenes_for_role(scenes, role, config, used_scene_ids, type_counts)

        if not candidates:
            break

        # En yüksek skorlu sahneyi seç (seed'e bağlı tie-break)
        candidates.sort(key=lambda x: x["_score"], reverse=True)

        # Top 3 arasından seed'e bağlı seç (çeşitlilik için)
        top_n = candidates[:min(3, len(candidates))]
        choice = rng.choice(top_n)

        scene = choice["_scene"]

        # İşaretle
        used_scene_ids.add(scene["scene_id"])
        ptype = scene.get("primary_type", "atmospheric")
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

        # Seçilen sahneyi kopyala ve narrative_role'ü ata
        clip = dict(scene)
        clip["narrative_role"] = role
        clip["actual_duration"] = clip.get("duration", 3.0)
        selected.append(clip)

    return selected


def _score_scenes_for_role(
    scenes: List[dict],
    role: str,
    config: dict,
    used_ids: set,
    type_counts: Dict[str, int],
) -> List[dict]:
    """Belirli bir narrative_role için sahne skorlama.

    Returns:
        {"_scene": scene, "_score": float} listesi
    """
    candidates = []
    preferred_types = config.get("preferred_types", [])
    arousal_min = config.get("arousal_min", 0.0)

    for scene in scenes:
        sid = scene.get("scene_id", -1)
        if sid in used_ids:
            continue

        ptype = scene.get("primary_type", "atmospheric")

        # Tip limit kontrolü
        if type_counts.get(ptype, 0) >= MAX_PER_TYPE:
            continue

        score = 0.0

        # 1. Narrative role eşleşmesi (en önemli)
        if scene.get("narrative_role") == role:
            score += 50.0
        elif _role_compatible(scene.get("narrative_role", ""), role):
            score += 20.0

        # 2. Arousal minimumu
        arousal = scene.get("arousal", 0.5)
        if arousal >= arousal_min:
            score += 15.0
        else:
            score -= 10.0

        # 3. Tip tercihi
        if ptype in preferred_types:
            score += 10.0 * preferred_types.count(ptype)

        # 4. Min tip garantisi
        if type_counts.get(ptype, 0) < MIN_PER_TYPE:
            score += 8.0

        # 5. Valence çeşitliliği bonusu
        valence = scene.get("valence", 0.0)
        if valence != 0:
            score += 2.0

        candidates.append({"_scene": scene, "_score": score})

    return candidates


def _role_compatible(scene_role: str, target_role: str) -> bool:
    """İki narrative role'ün uyumlu olup olmadığını kontrol et."""
    compatibility = {
        "hook": {"setup", "inciting"},
        "setup": {"hook", "inciting", "rising"},
        "inciting": {"setup", "rising", "hook"},
        "rising": {"inciting", "climax", "setup"},
        "climax": {"rising", "falling"},
        "falling": {"climax", "resolution"},
        "resolution": {"falling", "end"},
        "end": {"resolution", "falling"},
        "transition": set(),
    }
    return target_role in compatibility.get(scene_role, set())


# ─── Valence Zigzag ─────────────────────────────────────────────

def _apply_valence_zigzag(scenes: List[dict], rng: random.Random) -> List[dict]:
    """Ardışık sahneler arası valence değişimi zorunluluğu.

    Monoton valence zincirlerini kırar, duygusal dinamik yaratır.
    """
    if len(scenes) < 3:
        return scenes

    # Ardışık aynı işaretli valence'ları tespit et ve düzelt
    for i in range(1, len(scenes)):
        prev_val = scenes[i - 1].get("valence", 0)
        curr_val = scenes[i].get("valence", 0)

        # Aynı işaret ve yeterince yakınsa, zigzag zorla
        if (prev_val >= 0 and curr_val >= 0) or (prev_val < 0 and curr_val < 0):
            diff = abs(curr_val - prev_val)
            if diff < VALENCE_ZIGZAG_MIN:
                # İşaret değiştir
                new_val = -curr_val if curr_val != 0 else (-0.4 if curr_val >= 0 else 0.4)
                # Rastgele varyasyon ekle (seed'e bağlı)
                jitter = rng.uniform(-0.15, 0.15)
                scenes[i]["valence"] = round(max(-1.0, min(1.0, new_val + jitter)), 2)

    return scenes


# ─── Arousal Rampası ────────────────────────────────────────────

def _apply_arousal_ramp(
    scenes: List[dict],
    target_duration: float,
    rng: random.Random,
) -> List[dict]:
    """Son 30 saniyenin %70'inin yüksek arousal olmasını sağla.

    Yüksek arousal: climax, action sahneleri
    """
    if not scenes:
        return scenes

    # Toplam süreyi hesapla
    total = sum(s.get("actual_duration", s.get("duration", 3)) for s in scenes)

    # Son 30 saniyeyi bul
    final_30s_start = max(0, total - 30)

    # Şu anki son 30s durumunu hesapla
    current_time = 0
    final_scenes = []  # (index, scene) listesi

    for i, s in enumerate(scenes):
        dur = s.get("actual_duration", s.get("duration", 3))
        if current_time >= final_30s_start:
            final_scenes.append((i, s))
        current_time += dur

    if not final_scenes:
        return scenes

    # Yüksek arousal oranını hesapla
    high_arousal_count = sum(
        1 for _, s in final_scenes
        if s.get("arousal", 0) >= HIGH_AROUSAL_THRESHOLD
    )
    ratio = high_arousal_count / len(final_scenes) if final_scenes else 0

    # Yetersizse, düşük arousal sahnelerini yükselt
    if ratio < FINAL_30S_AROUSAL_RATIO:
        for idx, s in final_scenes:
            if s.get("arousal", 0) < HIGH_AROUSAL_THRESHOLD:
                # Arousal'ı artır (seed'e bağlı)
                boost = rng.uniform(0.15, 0.35)
                new_arousal = min(1.0, s.get("arousal", 0) + boost)
                scenes[idx]["arousal"] = round(new_arousal, 2)

    return scenes


# ─── Süre Kısıtı ────────────────────────────────────────────────

def _apply_duration_constraint(scenes: List[dict], target_duration: float) -> List[dict]:
    """Toplam süreyi hedefe göre kırp/ayarla."""
    if not scenes:
        return []

    total = sum(s.get("actual_duration", s.get("duration", 3)) for s in scenes)

    if total <= target_duration:
        return scenes

    # Fazla süreyi kırp (son sahnelerden başlayarak)
    excess = total - target_duration
    result = list(scenes)

    # Son sahnelerden başlayarak kırp
    for i in range(len(result) - 1, -1, -1):
        if excess <= 0:
            break
        current_dur = result[i].get("actual_duration", result[i].get("duration", 3))
        min_dur = 1.5
        if current_dur - excess >= min_dur:
            result[i]["actual_duration"] = round(current_dur - excess, 2)
            excess = 0
        else:
            new_dur = min_dur
            excess -= (current_dur - new_dur)
            result[i]["actual_duration"] = round(new_dur, 2)

    # Hala fazla varsa, en kısa sahneleri at
    total = sum(s.get("actual_duration", s.get("duration", 3)) for s in result)
    while total > target_duration and len(result) > 3:
        # En düşük skorlu sahneyi bul ve at
        result.sort(key=lambda x: x.get("arousal", 0) + abs(x.get("valence", 0)))
        removed = result.pop(0)
        total -= removed.get("actual_duration", removed.get("duration", 3))

    return result


# ─── Toplu Fonksiyonlar ─────────────────────────────────────────

def select_clips_from_analyses(
    analyses: List[dict],
    target_duration: float = 59.0,
    seed: int = 42,
    template: str = "hype",
) -> List[dict]:
    """Bir veya daha fazla analizden klip seç.

    Args:
        analyses: deep_analyzer çıktı listesi (zenginleştirilmiş sahneler)
        target_duration: Hedef süre
        seed: Rastgele tohum
        template: Şablon adı

    Returns:
        Seçilmiş klipler
    """
    return select_clips(analyses, target_duration, seed, template)


# ─── CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python selector.py <scenes_owl.json> [--seed 42] [--template hype]")
        sys.exit(1)

    scenes_file = sys.argv[1]

    seed = 42
    template = "hype"

    if "--seed" in sys.argv:
        seed = int(sys.argv[sys.argv.index("--seed") + 1])
    if "--template" in sys.argv:
        template = sys.argv[sys.argv.index("--template") + 1]

    with open(scenes_file, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    clips = select_clips(scenes, seed=seed, template=template)

    print(f"\n[selector] {len(clips)} klip seçildi:")
    for c in clips:
        print(f"  Scene {c['scene_id']}: {c.get('primary_type', '?')} "
              f"| valence={c.get('valence', 0):+.2f} "
              f"| arousal={c.get('arousal', 0):.2f} "
              f"| role={c.get('narrative_role', '?')} "
              f"| {c.get('actual_duration', c.get('duration', 0)):.1f}s")
