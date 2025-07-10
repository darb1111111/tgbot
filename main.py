import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from handlers import register_handlers
from db import init_db, close_db

# Load environment variables
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retrieve environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

# Validate environment variables
if not BOT_TOKEN or not WEBHOOK_URL:
    logger.error("BOT_TOKEN or WEBHOOK_URL not set in environment variables")
    raise ValueError("Missing required environment variables")

# Initialize Bot, Dispatcher, and FastAPI
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

# FastAPI Events
@app.on_event("startup")
async def on_startup():
    try:
        await init_db()
        register_handlers(dp)
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", secret_token=WEBHOOK_SECRET)
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
        await close_db()
        logger.info("Webhook deleted and database connection closed")
    except Exception as e:
        logger.error(f"Shutdown failed: {e}")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        # Verify webhook secret
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            logger.warning("Invalid webhook secret")
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
        
        # Process update
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return {"ok": False}