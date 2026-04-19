import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv()
import shared_data

# Load data at startup
shared_data.load_all_data()

# Import after loading data, so bot_core can access it
from bot_core import get_application
from admin_routes import router as admin_router

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    bot_app = get_application()
    
    logger.info("Initializing Telegram Bot...")
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram Bot started in background!")
    
    yield
    
    logger.info("Stopping Telegram Bot...")
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Telegram Bot stopped.")

app = FastAPI(title="Reiizam Store", lifespan=lifespan)

# Mount admin router
app.include_router(admin_router)

# Static files
app.mount('/static', StaticFiles(directory='static'), name='static')

if __name__ == '__main__':
    import uvicorn
    import os
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
