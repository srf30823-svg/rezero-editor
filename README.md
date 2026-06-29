# RE:ZERO SHORTS EDITOR

Otomatik YouTube Shorts editörü — sadece Re:Zero evrenine özel.

## Kurulum (Termux)

```bash
# 1. Ubuntu kur
pkg install proot-distro -y
proot-distro install ubuntu
proot-distro login ubuntu

# 2. Bağımlılıkları kur
apt update -y && apt install -y python3 python3-pip ffmpeg git
pip install opencv-python-headless librosa soundfile ffmpeg-python numpy click pyyaml rich scenedetect openai yt-dlp --break-system-packages

# 3. Repoyu klonla
git clone https://github.com/srf30823-svg/rezero-editor.git ~/rezero-editor
cd ~/rezero-editor

# 4. Klasörleri oluştur (Termux Android)
mkdir -p /data/data/com.termux/files/home/storage/shared/Download/rezero/input/{S01,S02,S03,S04,S05,music/action,music/emotional,music/dark}
mkdir -p /data/data/com.termux/files/home/storage/shared/Download/rezero/output/{shorts,timelines}
```

## Kullanım

```bash
# Kütüphaneyi tara
python main.py scan

# Otomatik edit (Owl Alpha yönetir)
python main.py edit --input /path/to/video.mp4 --duration 59

# Hızlı mod (ücretsiz, LLM yok)
python main.py edit --input /path/to/video.mp4 --no-llm

# Tüm sezon toplu edit
python main.py batch --season 1 --music track.mp3

# Cache yönetimi
python main.py cache --info
python main.py cache --clear
```

## Özellikler

- **Deep Analysis**: FFmpeg ile sahne tespiti (OpenCV'den hızlı, doğru)
- **Cache**: Her video bir kez analiz edilir → `~/.rezero_cache/`
- **Owl Alpha Director**: LLM ile akıllı klip sıralama ve müzik seçimi
- **Voice Ducking**: Side-chain compression ile diyalog koruma
- **Beat Sync**: Müzik ritmine senkronize kurgu
- **9:16 Format**: 1080x1920 dikey video, siyah bant dolgulu
- **Çoklu Sezon**: S01-S05 arası tüm bölümleri destekler

## API Keys (opsiyonel)

```bash
# OpenRouter ile Owl Alpha için
export OPENROUTER_API_KEY="sk-or-v1-..."
```

API key olmadan program kural tabanlı modda çalışır.

## Proje Yapısı

```
rezero-editor/
├── knowledge/          # Re:Zero bilgi bankası + Owl Director
│   ├── arcs.json
│   ├── characters.json
│   ├── lore_engine.py
│   └── owl_director.py     # 🦉 Owl Alpha LLM Director
├── video/              # Video analiz modülleri
│   ├── cache.py            # Analiz cache sistemi
│   ├── deep_analyzer.py    # Derin sahne analizi (FFmpeg)
│   ├── selector.py         # Stratejik klip seçimi
│   ├── extractor.py        # FFmpeg klip çıkarımı
│   └── ...
├── audio/              # Ses işleme modülleri
├── editor/             # Editör motorları
└── output/             # Çıkış klasörü
```

## Komutlar

| Komut | Açıklama |
|-------|----------|
| `scan` | Video kütüphanesini tara |
| `analyze --input video.mp4` | Derin video analizi |
| `edit --input video.mp4 --duration 59` | Shorts oluştur |
| `edit --input video.mp4 --no-llm` | LLM'siz hızlı mod |
| `export --timeline t.json --output v.mp4` | Timeline'dan render |
| `batch --season 1 --episodes 1-25` | Toplu Shorts üretimi |
| `best --season 1 --music t.mp3` | Mega Shorts (tüm sezon) |
| `cache --info` | Cache durumu |
| `cache --clear` | Cache temizle |
| `validate` | Sistem kontrolü |

## Cache Sistemi

Videolar ilk analizde `~/.rezero_cache/` altına JSON olarak kaydedilir.
Aynı video tekrar analiz edilmez — saniyeler içinde sonuç döner.
Cache, dosya boyutu + ilk 1MB hash ile benzersizdir.

```bash
python main.py cache --info       # Cache durumu
python main.py cache --clear      # Tüm cache temizle
python main.py cache --clear --video episode.mp4  # Tek video
```

## Test

```bash
python -m pytest tests/ -v
```
