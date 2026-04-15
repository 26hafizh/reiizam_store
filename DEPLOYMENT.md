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

## Start command

`python bot.py`

## Reliability notes

- The bot uses long polling with retry-friendly startup settings.
- For stricter 24/7 uptime on paid Railway plans, set restart policy to `Always` in the dashboard.
