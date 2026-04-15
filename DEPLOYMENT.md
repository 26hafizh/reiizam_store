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

## Start command

`python bot.py`
