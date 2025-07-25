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

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Переменные из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")

# Проверка наличия обязательных переменных
if not BOT_TOKEN or not WEBHOOK_URL:
    logger.critical("❌ BOT_TOKEN или WEBHOOK_URL не установлены в .env")
    raise ValueError("Отсутствуют обязательные переменные окружения")

# Инициализация бота, диспетчера и FastAPI
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

# Регистрация хендлеров сразу при создании диспетчера — так безопаснее
register_handlers(dp)

# При запуске сервера
@app.on_event("startup")
async def on_startup():
    try:
        await init_db()
        await bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook",
            secret_token=WEBHOOK_SECRET
        )
        logger.info("✅ Вебхук установлен")
    except Exception as e:
        logger.exception(f"❌ Ошибка старта: {e}")
        raise

# При завершении сервера
@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
        await close_db()
        logger.info("✅ Вебхук удалён, соединение с БД закрыто")
    except Exception as e:
        logger.exception(f"❌ Ошибка завершения: {e}")

# Обработка входящих обновлений от Telegram
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            logger.warning("⚠ Неверный секретный токен вебхука")
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

        data = await request.json()
        logger.debug(f"Получено обновление: {data}")  # Для отладки

        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.exception(f"❌ Ошибка при обработке запроса Telegram: {e}")
        return {"ok": False}
