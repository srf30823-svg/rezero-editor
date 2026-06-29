# RE:ZERO Video Edit Pipeline v2.0 — OWL Architecture

> Termux/Ubuntu Python video-edit pipeline, OpenRouter OWL modeliyle yükseltilmiş 5 modüllü mimari.

---

## Mimari Diyagram

```
                    INPUT (video.mp4)
                         |
                         v
+--------------------------------------------------+
|  1. video/scanner.py                              |
|     PySceneDetect (content + adaptive threshold)  |
|     Çıktı: scenes.jsonl                           |
|     Metadata: start, end, duration,               |
|              motion_magnitude, audio_rms,         |
|              speech_detected                      |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|  2. video/deep_analyzer.py                        |
|     OWL Vision-Language Model                     |
|     Batch: 10 sahne = 1 çağrı  (max 5 çağrı)     |
|     Çıktı: Çok boyutlu vektör                     |
|     {                                             |
|       valence, arousal, narrative_role,           |
|       primary_type, sub_type,                     |
|       audio_energy, visual_density                |
|     }                                             |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|  3. video/selector.py                             |
|     Deterministik seçim (seed-based)                |
|     Valence zigzag kısıtı                         |
|     Arousal rampası (son 30s %70+)                |
|     _pick_arc_aware(): narrative iskelet          |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|  4. knowledge/owl_director.py                     |
|     Şablon Kütüphanesi:                           |
|       hype, emotional, teaser, recap              |
|     OWL: Şablon seç + sahne ata (LLM sıralama yok)|
|     Çıktı: edit_plan.json                         |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|  5. editor/renderer.py                            |
|     Adaptif Kamera:                               |
|       action → zoom-in + shake                    |
|       dialogue → pan                              |
|       emotional → zoom-out                        |
|       atmospheric → drift                         |
|     Beat-sync: librosa ±80ms snap                 |
|     Renk: valence<0 desaturate, >0 saturate+5%    |
|     Ses: speech ducking (-18dB sidechaincompress) |
|     Altyazı: whisper.cpp + kelime highlight       |
+--------------------------------------------------+
                         |
                         v
                  OUTPUT (shorts.mp4)
```

---

## Veri Akışı

```
input.mp4 → [scanner] → scenes.jsonl
                           ↓
                    [deep_analyzer] ←→ OWL API (≤5 çağrı)
                           ↓
                    scenes_owl.json (vektörler)
                           ↓
                    [selector] ← seed + template
                           ↓
                    selected_clips.json
                           ↓
                    [owl_director] ←→ OWL API (1 çağrı)
                           ↓
                    edit_plan.json
                           ↓
                    [renderer] ←→ librosa beat_track
                           ↓
                    shorts.mp4
```

---

## Özellikler

| Özellik | v1.0 | v2.0 OWL |
|---------|------|----------|
| Skorlama | Tek `final_score` | Çok boyutlu vektör |
| Çeşitlilik | Rastgele | Seed-bazlı deterministik |
| Yapı | Sabit hook→build→climax→end | Şablon kütüphanesi |
| Kamera | Tek Ken Burns | Adaptif sahneler |
| Ses | Senkron değil | Beat-sync ±80ms |
| OWL Çağrısı | Her video 1+ çağrı | Max 5 çağrı/video |
| Cache | Yok | scene_id hash cache |

---

## Hızlı Başlangıç

```bash
# 1. Kurulum
pip install -r requirements.txt

# 2. API anahtarı
export OPENROUTER_API_KEY="sk-or-..."

# 3. Çalıştır
./run.sh input.mp4 --template hype --seed 42
```

---

## Modüller

| Modül | Dosya | Görev |
|-------|-------|-------|
| Scanner | `video/scanner.py` | Sahne tespiti |
| Deep Analyzer | `video/deep_analyzer.py` | OWL ile duygusal analiz |
| Selector | `video/selector.py` | Deterministik klip seçimi |
| Director | `knowledge/owl_director.py` | Şablonlu edit planı |
| Renderer | `editor/renderer.py` | Beat-sync render |

---

## Başarı Kriterleri

- [x] Aynı seed = byte-bayt aynı çıktı
- [x] Farklı seed = farklı ama kaliteli edit
- [x] Beat-sync ±80ms
- [x] ≤5 OWL çağrısı/video
- [x] 5dk kaynak → 2dk işlem
