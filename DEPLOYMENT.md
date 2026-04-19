# Deployment Notes

## Recommended setup

This bot can run well as a small always-on worker on Railway because it only needs:

- Python runtime
- environment variables
- outbound internet access for Telegram polling

## Storage recommendation for business use

The current bot is stateless. It does not store product data, photos, or customer records on disk yet.

If you later want large and durable storage for:

- product images
- invoice files
- customer documents
- backup data

do not rely on app local disk alone. Use external object storage such as an S3-compatible bucket and keep the bot app separate from the files.

## Railway environment variables

Set these in the deploy platform:

- `BOT_TOKEN`
- `WA_NUMBER`
- `STORE_NAME`
- `RESTART_DELAY_SECONDS=5` (optional)

## Admin Panel

**Local Dev:**
```
pip install -r admin/requirements.txt
cd admin
uvicorn app:app --reload --port 8001
```
Visit http://localhost:8001 (admin/admin)

**Usage:**
- /config: Edit store settings (saved to config.json)
- /products: Full CRUD categories/items
- /export: JSON for bot.py

## Bot Integration

Bot now loads `admin/products.json` automatically.

## Start commands

**Bot only:**
```
python bot.py
```

**Admin + Bot:**
Terminal 1: `cd admin && uvicorn app:app --reload`
Terminal 2: `python bot.py`

## Reliability notes

- The bot uses long polling with retry-friendly startup settings.
- For stricter 24/7 uptime on paid Railway plans, set restart policy to `Always` in the dashboard.
