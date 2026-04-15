# reiizam store Telegram Bot

Bot Telegram katalog produk premium yang mengarahkan pembeli ke WhatsApp admin dengan pesan order otomatis.

## Isi paket
- `bot.py` — source code bot
- `requirements.txt` — dependency Python
- `.env.example` — contoh environment variable
- `Dockerfile` — alternatif deploy berbasis container
- `railway.json` — konfigurasi start command Railway

## Cara jalankan lokal
1. Install Python 3.10+.
2. Install dependency:
   ```bash
   pip install -r requirements.txt
   ```
3. Buat file `.env` atau set environment variables:
   ```env
   BOT_TOKEN=ISI_TOKEN_BOT_KAMU
   WA_NUMBER=6285126019233
   STORE_NAME=reiizam store
   ```
4. Jalankan:
   ```bash
   python bot.py
   ```

## Deploy 24/7 di Railway
1. Upload folder ini ke GitHub.
2. Di Railway, buat project baru lalu pilih **Deploy from GitHub repo**.
3. Tambahkan environment variables:
   - `BOT_TOKEN`
   - `WA_NUMBER`
   - `STORE_NAME`
4. Railway bisa memakai start command `python bot.py`. File `railway.json` juga sudah menyiapkannya.
5. Setelah deploy berhasil, bot akan berjalan terus selama servicenya aktif.

## Catatan
- Nomor WhatsApp harus pakai format internasional tanpa `+`.
- Token bot Telegram didapat dari `@BotFather`.
- Bot ini memakai polling, jadi tidak perlu webhook tambahan.
