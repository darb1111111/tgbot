import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from handlers import register_handlers
from db import init_db, close_db

# Загрузка переменных окружения
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Получение переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

# Проверка переменных окружения
if not BOT_TOKEN or not WEBHOOK_URL:
    logger.error("BOT_TOKEN или WEBHOOK_URL не установлены в переменных окружения")
    raise ValueError("Отсутствуют необходимые переменные окружения")

# Инициализация Bot, Dispatcher и FastAPI
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

# События FastAPI
@app.on_event("startup")
async def on_startup():
    try:
        await init_db()
        register_handlers(dp)
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", secret_token=WEBHOOK_SECRET)
        logger.info("Вебхук успешно установлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        raise

@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
        await close_db()
        logger.info("Вебхук удален и соединение с базой данных закрыто")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        # Проверка секрета вебхука
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            logger.warning("Недействительный секрет вебхука")
            raise HTTPException(status_code=403, detail="Недействительный секрет вебхука")

        # Обработка обновления
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return {"ok": False}