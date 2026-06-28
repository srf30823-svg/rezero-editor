# RE:ZERO SHORTS EDITOR

Tamamen otomatik bir YouTube Shorts video editörü. SADECE Re:Zero evrenine özel.

## Kullanım

```bash
# Video analizi
python main.py analyze --input video.mp4

# Shorts oluşturma
python main.py edit --input video.mp4 --music track.mp3 --duration 59

# Final export
python main.py export --timeline timeline.json --output shorts.mp4
```

## Özellikler

- FFmpeg ile kare kare video analizi
- OpenCV ile sahne değişikliği ve aksiyon tespiti
- librosa ile müzik beat tespiti ve drop analizi
- Re:Zero lore bilgisiyle sahne puanlama (Rem sahnesi > random sahne)
- Beat'e senkronize otomatik kurgu
- 9:16 1080x1920 dikey format export

## Gereksinimler

```bash
pip install -r requirements.txt
```

## Proje Yapısı

```
rezero-editor/
├── knowledge/     # Re:Zero bilgi bankası
├── video/         # Video analiz modülleri
├── audio/         # Ses işleme modülleri
├── editor/        # Editör motorları
└── output/        # Çıkış klasörü
```