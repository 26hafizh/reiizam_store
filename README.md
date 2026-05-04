# reiizam store Telegram Bot

Bot Telegram katalog produk premium yang mengarahkan pembeli ke WhatsApp admin dengan pesan order otomatis yang lebih rapi, cepat, dan nyaman dipakai.

## Isi paket
- `main.py` - aplikasi FastAPI untuk bot + dashboard admin
- `bot.py` - mode polling bot saja untuk jalankan lokal sederhana
- `bot_core.py` - handler dan tampilan bot Telegram
- `requirements.txt` - dependency Python
- `.env.example` - contoh environment variable
- `railway.toml` - konfigurasi start command Railway

## Fitur utama
- Tampilan chat Telegram lebih rapi dan terasa lebih premium
- Tombol navigasi lebih interaktif dan responsif
- User bisa ketik nama produk seperti `ChatGPT`, `Canva`, atau `Netflix`
- Template chat WhatsApp lebih profesional untuk bantu order lebih cepat
- Siap dipakai untuk deploy 24/7 dengan polling yang lebih stabil

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
   RESTART_DELAY_SECONDS=5
   ADMIN_BASE_PATH=/reiizam-control-room
   ADMIN_SESSION_SECRET=ganti_dengan_random_panjang
   ```
4. Jalankan:
   ```bash
   python main.py
   ```
   Dashboard admin tersedia di `http://localhost:8080/reiizam-control-room`.

   Jika hanya butuh bot Telegram tanpa dashboard:
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
   - `RESTART_DELAY_SECONDS=5` (opsional)
4. Railway memakai start command dari `railway.toml`:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. Setelah deploy berhasil, bot akan berjalan terus selama servicenya aktif.

## Deploy gratis di Cloudflare Workers
Cloudflare Workers adalah opsi gratis yang lebih aman untuk bot ini karena memakai webhook dan tidak perlu server polling 24/7.

1. Buat/login akun Cloudflare.
2. Jalankan dari root repo:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy-cloudflare-worker.ps1
   ```
3. Ikuti login Cloudflare yang dibuka oleh Wrangler.
4. Setelah deploy dan webhook aktif, hentikan bot lokal:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\stop-local-bot.ps1
   ```

Kode Worker ada di `cloudflare-worker/`. Endpoint health setelah deploy: `/health`.

## Admin Telegram
- Ketik `/myid` ke bot untuk melihat Telegram ID kamu.
- Set `ADMIN_TELEGRAM_ID` di environment atau `data/config.json`, lalu restart bot.
- Setelah itu ketik `/admin` untuk mengelola produk, harga, dan nomor WhatsApp dari Telegram.

## Catatan
- Nomor WhatsApp harus pakai format internasional tanpa `+`.
- Token bot Telegram didapat dari `@BotFather`.
- Lokal tanpa domain memakai polling. Railway memakai webhook otomatis dari domain Railway.
- Font asli Telegram tidak bisa diganti dari kode bot, jadi perbaikan tampilan difokuskan ke layout, struktur pesan, tombol, dan template order.
