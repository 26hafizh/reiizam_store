# Reiizam Store Telegram Bot on Cloudflare Workers

Cloudflare Workers version of the Telegram bot. It uses Telegram webhook mode, so it does not need a 24/7 polling server.

## What Runs Here

- `/telegram/webhook` receives Telegram updates.
- `/health` checks Worker health.
- Product data is imported from `../data/products.json`.
- WhatsApp order links use `WA_NUMBER` from `wrangler.toml`.
- `BOT_TOKEN` and `WEBHOOK_SECRET` must be stored as Cloudflare Worker secrets.

## Deploy

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-cloudflare-worker.ps1
```

The script will:

1. Ask Wrangler to log in to Cloudflare if needed.
2. Upload `BOT_TOKEN` and `WEBHOOK_SECRET` as Worker secrets.
3. Deploy the Worker.
4. Register the Telegram webhook.

After webhook mode is active, stop any local polling bot:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-local-bot.ps1
```

## Manual Webhook Setup

If the deploy script cannot detect the Worker URL, set the webhook manually:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\set-cloudflare-webhook.ps1 -WorkerUrl https://reiizam-store-bot.YOUR_SUBDOMAIN.workers.dev -SecretToken YOUR_WEBHOOK_SECRET
```

## Notes

- Do not run local polling and webhook hosting for the same bot token at the same time.
- Do not commit `.env`, `.dev.vars`, or Cloudflare secret values.
- Cloudflare Workers Free has daily request limits, but it is enough for a small Telegram shop bot.
