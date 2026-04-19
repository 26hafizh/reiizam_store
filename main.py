import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update
from dotenv import load_dotenv

load_dotenv()

import shared_data
shared_data.load_all_data()

from bot_core import get_application
from admin_routes import router as admin_router

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Railway otomatis set RAILWAY_PUBLIC_DOMAIN → pakai webhook
# Lokal tidak ada → pakai polling
RAILWAY_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
WEBHOOK_PATH   = '/telegram/webhook'
WEBHOOK_URL    = f'https://{RAILWAY_DOMAIN}{WEBHOOK_PATH}' if RAILWAY_DOMAIN else None

bot_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    bot_app = get_application()

    await bot_app.initialize()
    await bot_app.start()

    if WEBHOOK_URL:
        await bot_app.bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        logger.info('Webhook mode aktif: %s', WEBHOOK_URL)
    else:
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info('Polling mode aktif (lokal).')

    yield

    logger.info('Shutting down bot...')
    if WEBHOOK_URL:
        await bot_app.bot.delete_webhook()
    else:
        await bot_app.updater.stop()

    await bot_app.stop()
    await bot_app.shutdown()
    logger.info('Bot stopped.')


app = FastAPI(title='Reiizam Store', lifespan=lifespan)


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Endpoint yang menerima update dari Telegram (production/webhook mode)."""
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return JSONResponse({'ok': True})


app.include_router(admin_router)
app.mount('/static', StaticFiles(directory='static'), name='static')
