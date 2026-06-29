# RE:ZERO SHORTS EDITOR

Otomatik YouTube Shorts editörü — sadece Re:Zero evrenine özel.
LLM destekli (Owl Alpha), trace.moe sahne tanıma, yüz tespiti ve sinematik geçişler.

## Kurulum

```bash
# Bağımlılıklar
apt install -y python3 python3-pip ffmpeg git
pip install opencv-python-headless librosa numpy click pyyaml rich openai requests

# Klonla
git clone https://github.com/srf30823-svg/rezero-editor.git
cd rezero-editor

# Klasörler
mkdir -p input/{S01,S02,S03,S04,S05,music} output/shorts
```

## Kullanım

```bash
# Shorts oluştur (trace.moe + yüz tespiti ile)
python main.py edit -i episode.mp4 -d 59

# Hızlı mod (trace.moe + LLM yok)
python main.py edit -i episode.mp4 -d 59 --no-trace --no-llm

# Çoklu thread (CPU render hızı)
python main.py edit -i episode.mp4 -d 59 --threads 4

# Toplu işlem
python main.py batch --season 1 --episodes 1-25

# Sistem kontrol
python main.py validate
```

## Özellikler

| Özellik | Açıklama |
|---------|----------|
| **Deep Analysis** | FFmpeg sahne tespiti, 153 sahne / 36sn |
| **Cache** | `~/.rezero_cache/` — bir kez analiz, milisaniyede yükle |
| **Owl Alpha** | OpenRouter LLM ile akıllı klip sıralama + müzik |
| **trace.moe** | Anime sahne tanıma, %99+ benzerlik |
| **Yüz Tespiti** | lbpcascade_animeface ile anime yüz bulma |
| **Re:Zero Lore DB** | Kritik anlar (Rem itirafı, Echidna sözleşme vs.) |
| **Voice Ducking** | Diyalog ses 3.0x, otomatik müzik kısma |
| **Beat Sync** | Müzik ritmine senkronize kurgu (librosa) |
| **Ken Burns** | Zoom-in/out, x/y center tracking, titreme yok |
| **16 Geçiş** | Sahne tipine göre wipeleft, dissolve, smoothleft, fade |
| **Color Grading** | Action/emotional/dialogue/atmospheric tonlama |
| **HW Accel** | CUDA/VAAPI/Videotoolbox auto-detect |
| **480p Crop** | Siyah bar yok, scale=increase + crop |

## Parametreler

```bash
# Tüm opsiyonlar
python main.py edit -i video.mp4 \
  -m music.mp3 \           # Müzik (belirtilmezse otomatik)
  -d 59 \                  # Hedef süre (saniye)
  -o output/shorts.mp4 \   # Çıkış dosyası
  -l tr \                  # Altyazı dili (tr/en)
  --no-subs \              # Altyazısız
  --no-llm \               # LLM'siz (kural tabanlı)
  --no-trace \             # trace.moe'suz (hızlı)
  --threads 4 \            # FFmpeg thread (CPU hızı)
  --no-hwaccel             # HW ivmesiz
```

## API Key (opsiyonel)

```bash
# config.yaml'a yaz veya export et
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Olmadan kural tabanlı modda çalışır.

## Proje Yapısı

```
rezero-editor/
├── main.py                 # CLI
├── config.yaml             # Yapılandırma
├── knowledge/              # Bilgi bankası
│   ├── owl_director.py     # 🦉 Owl Alpha LLM
│   ├── scene_identifier.py # trace.moe API
│   ├── face_analyzer.py    # Anime yüz tespiti
│   └── rezero_lore_db.py   # Kritik anlar DB
├── video/                  # Video analizi
│   ├── deep_analyzer.py    # Sahne + yüz + trace
│   ├── selector.py         # Klip seçimi
│   └── cache.py            # Cache sistemi
├── audio/                  # Ses işleme
│   ├── music_selector.py
│   ├── voice_ducking.py
│   └── beat_detector.py
├── editor/                 # Editör motoru
│   ├── renderer.py         # FFmpeg render (crop, Ken Burns, 16 geçiş, hwaccel)
│   ├── effects.py          # Efekt motoru (flash, shake, grade)
│   ├── captions.py         # SRT/ASS altyazı (KeyMoment stili)
│   └── timeline.py         # Timeline oluşturma
└── output/                 # Çıkışlar
```

## Test

```bash
python -m pytest tests/ -v
python main.py validate      # Sistem kontrolü
```
