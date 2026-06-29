#!/bin/bash
# RE:ZERO Video Edit Pipeline v2.0 — OWL Architecture
# Kullanım: ./run.sh input.mp4 --template hype --seed 42
#
# Pipeline Akışı:
#   1. scanner     → scenes.jsonl (sahne tespiti)
#   2. deep_analyzer → scenes_owl.json (çok boyutlu analiz)
#   3. selector    → selected_clips.json (deterministik seçim)
#   4. owl_director → edit_plan.json (şablon + plan)
#   5. renderer    → output.mp4 (beat-sync render)

set -euo pipefail

# ─── Varsayılanlar ──────────────────────────────────────────────
TEMPLATE="hype"
SEED=42
MUSIC=""
SUBS=""
THREADS=2
NO_HWACCEL=""
NO_OWL=""

# ─── Argüman Ayrıştırma ─────────────────────────────────────────
INPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --template)
            TEMPLATE="$2"
            shift 2
            ;;
        --seed)
            SEED="$2"
            shift 2
            ;;
        --music)
            MUSIC="$2"
            shift 2
            ;;
        --subs)
            SUBS="$2"
            shift 2
            ;;
        --threads)
            THREADS="$2"
            shift 2
            ;;
        --no-hwaccel)
            NO_HWACCEL="1"
            shift
            ;;
        --no-owl)
            NO_OWL="1"
            shift
            ;;
        --help)
            echo "RE:ZERO Video Edit Pipeline v2.0"
            echo ""
            echo "Kullanım: ./run.sh <input.mp4> [SEÇENEKLER]"
            echo ""
            echo "Seçenekler:"
            echo "  --template <hype|emotional|teaser|recap>  Edit şablonu (varsayılan: hype)"
            echo "  --seed <sayı>                             Rastgele tohum (varsayılan: 42)"
            echo "  --music <müzik.mp3>                       Arka plan müziği"
            echo "  --subs <altyazı.srt>                      Altyazı dosyası"
            echo "  --threads <sayı>                          FFmpeg thread (varsayılan: 2)"
            echo "  --no-hwaccel                              Donanım ivmesini devre dışı bırak"
            echo "  --no-owl                                  OWL API kullanma (heuristic mod)"
            echo "  --help                                    Bu yardım mesajı"
            echo ""
            echo "Örnekler:"
            echo "  ./run.sh video.mp4 --template emotional --seed 123"
            echo "  ./run.sh video.mp4 --template hype --music beat.mp3 --seed 42"
            exit 0
            ;;
        -*)
            echo "Bilinmeyen seçenek: $1"
            echo "Yardım için: ./run.sh --help"
            exit 1
            ;;
        *)
            if [[ -z "$INPUT" ]]; then
                INPUT="$1"
            fi
            shift
            ;;
    esac
done

# ─── Doğrulama ──────────────────────────────────────────────────
if [[ -z "$INPUT" ]]; then
    echo "Hata: Giriş video dosyası belirtilmedi"
    echo "Kullanım: ./run.sh input.mp4 [SEÇENEKLER]"
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Hata: Dosya bulunamadı: $INPUT"
    exit 1
fi

# Şablon doğrulama
if [[ ! "$TEMPLATE" =~ ^(hype|emotional|teaser|recap)$ ]]; then
    echo "Hata: Geçersiz şablon: $TEMPLATE"
    echo "Geçerli şablonlar: hype, emotional, teaser, recap"
    exit 1
fi

# Müzik dosyası doğrulama
if [[ -n "$MUSIC" && ! -f "$MUSIC" ]]; then
    echo "Hata: Müzik dosyası bulunamadı: $MUSIC"
    exit 1
fi

# Altyazı dosyası doğrulama
if [[ -n "$SUBS" && ! -f "$SUBS" ]]; then
    echo "Hata: Altyazı dosyası bulunamadı: $SUBS"
    exit 1
fi

# ─── Çıkış Yolları ──────────────────────────────────────────────
INPUT_NAME="$(basename "$INPUT" .mp4)"
OUTPUT_DIR="output/${INPUT_NAME}_${TEMPLATE}_seed${SEED}"
mkdir -p "$OUTPUT_DIR"

SCENES_JSONL="$OUTPUT_DIR/1_scenes.jsonl"
SCENES_OWL="$OUTPUT_DIR/2_scenes_owl.json"
SELECTED="$OUTPUT_DIR/3_selected_clips.json"
EDIT_PLAN="$OUTPUT_DIR/4_edit_plan.json"
OUTPUT_VIDEO="$OUTPUT_DIR/${INPUT_NAME}_${TEMPLATE}_seed${SEED}.mp4"

# ─── Python Yolu ────────────────────────────────────────────────
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"

echo "═══════════════════════════════════════════════════"
echo "  RE:ZERO Video Edit Pipeline v2.0 — OWL"
echo "═══════════════════════════════════════════════════"
echo "  Input:    $INPUT"
echo "  Template: $TEMPLATE"
echo "  Seed:     $SEED"
echo "  Output:   $OUTPUT_VIDEO"
[[ -n "$MUSIC" ]] && echo "  Music:    $MUSIC"
[[ -n "$SUBS" ]] && echo "  Subs:     $SUBS"
echo "───────────────────────────────────────────────────"

# ─── Adım 1: Scanner ────────────────────────────────────────────
echo ""
echo "[1/5] 🔍 Sahne tespiti..."
$PYTHON -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
from video.scanner import scan_video
scenes = scan_video('${INPUT}', '${SCENES_JSONL}')
print(f'[scanner] {len(scenes)} sahne bulundu')
"

# ─── Adım 2: Deep Analyzer ──────────────────────────────────────
echo ""
echo "[2/5] 🧠 OWL derin analiz..."
if [[ -n "$NO_OWL" ]]; then
    echo "      (Heuristic mod — OWL devre dışı)"
fi

$PYTHON -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
import json
from video.scanner import load_scenes
from video.deep_analyzer import deep_analyze_video

scenes = load_scenes('${SCENES_JSONL}')
analyses = deep_analyze_video('${INPUT}', scenes, use_owl=${NO_OWL:+False:-True})

with open('${SCENES_OWL}', 'w', encoding='utf-8') as f:
    json.dump(analyses, f, ensure_ascii=False, indent=2)
print(f'[deep_analyzer] {len(analyses)} sahne analiz edildi')
"

# ─── Adım 3: Selector ───────────────────────────────────────────
echo ""
echo "[3/5] 🎯 Deterministik klip seçimi (seed=${SEED})..."
$PYTHON -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
import json
from video.selector import select_clips

with open('${SCENES_OWL}', 'r', encoding='utf-8') as f:
    scenes = json.load(f)

clips = select_clips(scenes, target_duration=59.0, seed=${SEED}, template='${TEMPLATE}')

with open('${SELECTED}', 'w', encoding='utf-8') as f:
    json.dump(clips, f, ensure_ascii=False, indent=2)
print(f'[selector] {len(clips)} klip seçildi')
"

# ─── Adım 4: OWL Director ───────────────────────────────────────
echo ""
echo "[4/5] 🎬 Edit planı oluşturma..."
$PYTHON -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
import json
from knowledge.owl_director import create_edit_plan

with open('${SELECTED}', 'r', encoding='utf-8') as f:
    clips = json.load(f)

plan = create_edit_plan(clips, template='${TEMPLATE}', use_owl=${NO_OWL:+False:-True})

with open('${EDIT_PLAN}', 'w', encoding='utf-8') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)
print(f'[owl_director] Template: {plan[\"template\"]}, {len(plan[\"ordered_clips\"])} klip')
"

# ─── Adım 5: Renderer ───────────────────────────────────────────
echo ""
echo "[5/5] 🎥 Video render..."
RENDER_ARGS=""
[[ -n "$MUSIC" ]] && RENDER_ARGS="--music '${MUSIC}'"
[[ -n "$SUBS" ]] && RENDER_ARGS="${RENDER_ARGS} --subs '${SUBS}'"

$PYTHON -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
import json
from editor.renderer import render_edit

with open('${EDIT_PLAN}', 'r', encoding='utf-8') as f:
    plan = json.load(f)

result = render_edit(
    plan,
    '${OUTPUT_VIDEO}',
    music_path='${MUSIC}' if '${MUSIC}' else None,
    subtitle_path='${SUBS}' if '${SUBS}' else None,
    seed=${SEED},
    threads=${THREADS},
    hwaccel=${NO_HWACCEL:+False:-True},
)
print(f'[renderer] Çıktı: {result}')
"

# ─── Tamamlandı ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✓ TAMAMLANDI"
echo "═══════════════════════════════════════════════════"
echo "  Video: ${OUTPUT_VIDEO}"
echo "  Ara dosyalar: ${OUTPUT_DIR}/"
echo "───────────────────────────────────────────────────"

# Dosya boyutu
if [[ -f "$OUTPUT_VIDEO" ]]; then
    SIZE=$(du -h "$OUTPUT_VIDEO" | cut -f1)
    echo "  Boyut: $SIZE"
fi

echo ""
echo "Şablon: $TEMPLATE | Seed: $SEED"
echo "Aynı seed ile tekrar çalıştırırsanız BİREBİR aynı çıktı üretilir."
