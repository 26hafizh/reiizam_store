#!/bin/bash
# Start Telegram bot in the background
python bot.py &

# Start FastAPI admin panel in the foreground
# Railway passes the $PORT environment variable automatically
uvicorn admin.app:app --host 0.0.0.0 --port ${PORT:-8000}
