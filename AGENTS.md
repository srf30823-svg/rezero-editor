# AGENTS.md

Her seferinde oku: Bu dosya, RE:ZERO SHORTS EDITOR projesinin geliştirme kurallarını içerir.

## Proje Mimarisi
- Tamamen otomatik YouTube Shorts video editörü
- SADECE Re:Zero evreni içerikleri için çalışır
- 9:16 1080x1920 dikey format export hedefi

## Geliştirme Kuralları
- Her modül bitmeden commit etme
- Broken code commit etme
- Her fonksiyonun docstring'i olsun
- Hata mesajları Türkçe ve anlaşılır olsun
- Context biterse CHECKPOINT.md'yi güncelle ve dur

## Dosya Yapısı
```
rezero-editor/
├── AGENTS.md               # Bu dosya
├── CHECKPOINT.md           # İşlem durumu
├── README.md
├── requirements.txt
├── config.yaml
├── main.py                 # CLI entry point
├── knowledge/              # Re:Zero bilgi bankası
├── video/                  # Video analiz modülleri
├── audio/                  # Ses işleme modülleri
├── editor/                 # Editör motorları
└── output/                 # Çıkış klasörü
```

## Komutlar
- `python main.py analyze --input video.mp4` - Video analizi
- `python main.py edit --input video.mp4 --duration 59` - Shorts edit (müzik otomatik seçilir)
- `python main.py edit --input video.mp4 --music track.mp3 --duration 59` - Özel müzik ile Shorts edit
- `python main.py export --timeline timeline.json --output shorts.mp4` - Final render