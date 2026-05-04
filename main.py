import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update
from dotenv import load_dotenv

# Load ENV
load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env')

import shared_data
shared_data.load_all_data()

from bot_core import get_application, post_init
from admin_routes import router as admin_router

# Logging
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def log_update_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Unhandled error while processing webhook update")

# Railway Domain Detection
# RAILWAY_PUBLIC_DOMAIN biasanya hanya 'xxx.up.railway.app'
# RAILWAY_STATIC_URL biasanya 'xxx.up.railway.app'
DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN') or os.getenv('RAILWAY_STATIC_URL') or ''
DOMAIN = DOMAIN.strip().replace('https://', '').replace('http://', '')

WEBHOOK_PATH = '/telegram/webhook'
WEBHOOK_URL = f'https://{DOMAIN}{WEBHOOK_PATH}' if DOMAIN else None

bot_app = None
bot_started = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app, bot_started
    logger.info("=== STARTING APPLICATION LIFESPAN ===")
    candidate_app = None
    
    try:
        candidate_app = get_application()
        await candidate_app.initialize()
        await post_init(candidate_app)
        await candidate_app.start()
        bot_app = candidate_app

        if WEBHOOK_URL:
            # Set Webhook
            success = await bot_app.bot.set_webhook(
                url=WEBHOOK_URL, 
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                max_connections=40,
            )
            if success:
                logger.info(f"✅ WEBHOOK BERHASIL DISET: {WEBHOOK_URL}")
            else:
                raise RuntimeError(f"Gagal set webhook: {WEBHOOK_URL}")
        else:
            # Fallback Polling (Lokal)
            await bot_app.updater.start_polling(drop_pending_updates=True)
            logger.info("ℹ️ POLLING MODE AKTIF (Lokal/No Domain)")

        bot_started = True

    except Exception as e:
        logger.exception(f"💥 FATAL ERROR SAAT STARTUP: {e}")
        bot_started = False
        bot_app = None
        if candidate_app:
            try:
                await candidate_app.stop()
            except Exception:
                pass
            try:
                await candidate_app.shutdown()
            except Exception:
                pass
        raise

    yield

    logger.info("=== SHUTTING DOWN APPLICATION ===")
    try:
        if bot_app:
            if not WEBHOOK_URL:
                await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            bot_started = False
    except Exception as e:
        logger.error(f"Error saat shutdown: {e}")

app = FastAPI(title='Reiizam Store', lifespan=lifespan)

@app.get("/health")
async def health_check():
    """Cek apakah bot dan server sehat."""
    status = {
        "server": "online",
        "bot_initialized": bot_app is not None,
        "bot_started": bot_started,
        "webhook_url": WEBHOOK_URL,
        "domain": DOMAIN
    }
    return status

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Endpoint penerima pesan Telegram."""
    if not bot_app:
        logger.error("Webhook hit tapi bot_app belum siap!")
        return Response(status_code=503)

    try:
        data = await request.json()
        # Log incoming update (opsional, untuk debug)
        # logger.info(f"Incoming Update: {data}")
        
        update = Update.de_json(data, bot_app.bot)
        
        # Ack webhook quickly so Telegram can deliver the next update without
        # waiting for slower message edits, photo uploads, or external API calls.
        task = asyncio.create_task(bot_app.process_update(update))
        task.add_done_callback(log_update_task_result)
        
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# Dashboard & Static Files
app.include_router(admin_router)
app.mount('/static', StaticFiles(directory='static'), name='static')

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
