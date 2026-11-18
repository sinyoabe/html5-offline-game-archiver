# Universal HTML5 Offline Game Archiver

Alat berbasis Python untuk mengunduh, mengarsipkan, mendeteksi *tech stack* (engine, bahasa, dan library), serta menjalankan game HTML5 secara *offline* (kompatibel dengan Windows 7 via server lokal).

## Fitur Utama
- **Auto-Crawler & Asset Extractor**: Mendukung Construct 2, Construct 3, CreateJS, GameMaker: HTML5, dan HTML5 Canvas.
- **Tech Stack Fingerprinting**: Mendeteksi engine dan library otomatis lalu menyimpannya ke `database_game.json`.
- **Offline Runner**: Menghasilkan skrip batch & PowerShell lokal pada port `8899`.

## Cara Menjalankan
```bash
python3 game_downloader.py

