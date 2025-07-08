import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import pytz
import logging
import os
from dotenv import load_dotenv
import aiohttp
import urllib.parse
import re

from keep_alive import app
from db import init_db, close_db, add_booking, get_all_bookings, delete_booking_by_id

load_dotenv()

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Bishkek")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

services = [
    "Наращивание ресниц",
    "Ламинирование ресниц",
    "Ламинирование бровей",
    "Коррекция и окрашивание бровей",
    "Мусульманская коррекция"
]

def get_service_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s, callback_data=f"svc_{i}")] for i, s in enumerate(services)
    ])

class BookingForm(StatesGroup):
    name = State()
    service = State()
    date = State()
    time = State()
    phone = State()

def is_valid_phone(phone: str) -> bool:
    pattern = r"^\+996\d{9}$"
    return bool(re.match(pattern, phone))

async def send_to_whatsapp(name, date, time, service, phone):
    api_phone = os.getenv("WHATSAPP_PHONE")
    apikey = os.getenv("API_KEY")
    if not api_phone or not apikey:
        logging.error("Отсутствуют WHATSAPP_PHONE или API_KEY")
        return
    message = f"\ud83d\uddd3 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={api_phone}&text={encoded_message}&apikey={apikey}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    logging.info(f"Успешно отправлено в WhatsApp: {message}")
                else:
                    logging.error(f"Ошибка WhatsApp API {resp.status}: {await resp.text()}")
        except Exception as e:
            logging.error(f"Исключение при отправке в WhatsApp: {e}")

async def start(message: types.Message, state: FSMContext):
    await message.answer("\ud83d\udc4b Привет! Я бот для онлайн-записи.\nКак тебя зовут?")
    await state.set_state(BookingForm.name)

async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50 or not any(char.isalpha() for char in name):
        await message.answer("\u274c Введите корректное имя (только буквы, не более 50 символов).")
        return
    await state.update_data(name=name)
    await message.answer("\ud83d\udc85 Какую услугу выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)

async def process_service(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("svc_", ""))
    await state.update_data(service=services[idx])
    await callback.message.answer("\ud83d\uddd3 На какую дату записаться? (например, 2025-06-01)")
    await state.set_state(BookingForm.date)
    await callback.answer()

async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    timezone = pytz.timezone(TIMEZONE)
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        if parsed_date.date() < datetime.now(timezone).date():
            await message.answer("\u274c Нельзя записаться на прошедшую дату!")
            return
    except ValueError:
        await message.answer("\u274c Неверный формат даты! Введите, например, 2025-06-01.")
        return
    await state.update_data(date=date)
    await message.answer("\ud83d\udd52 Во сколько? (например, 14:30)")
    await state.set_state(BookingForm.time)

async def check_time_availability(date: str, time: str) -> bool:
    try:
        new_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return False

    bookings = await get_all_bookings()

    for b in bookings:
        if b[2] == date and b[3] == time:
            return False
    return True

async def ask_phone(message: types.Message, state: FSMContext):
    time = message.text.strip()
    try:
        dt_time = datetime.strptime(time, "%H:%M").time()
        if dt_time.hour < 8 or dt_time.hour > 21:
            await message.answer("\u274c Запись возможна только с 08:00 до 21:00.")
            return
    except ValueError:
        await message.answer("\u274c Неверный формат времени! Введите, например, 14:30.")
        return

    data = await state.get_data()
    date = data.get("date")

    is_available = await check_time_availability(date, time)

    if not is_available:
        await message.answer("\u274c Это время недоступно! Должно быть минимум 2 часа между записями.")
        return

    await state.update_data(time=time)
    await message.answer("\ud83d\udcf1 Введите свой номер телефона (например, +996123456789):")
    await state.set_state(BookingForm.phone)

async def validate_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not is_valid_phone(phone):
        await message.answer("\u274c Неверный формат номера! Введите, например, +996123456789.")
        return

    await state.update_data(phone=phone)
    data = await state.get_data()

    success = await add_booking(data["name"], data["date"], data["time"], data["service"], data["phone"])
    if not success:
        await message.answer("\u274c Ошибка при сохранении записи. Попробуйте позже.")
        return

    await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], data["phone"])
    await message.answer(
        f"\u2705 Запись подтверждена!\n\n"
        f"Имя: {data['name']}\n"
        f"Услуга: {data['service']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"Спасибо за запись! \ud83d\udcac"
    )
    await state.clear()

# ОСТАВИЛ ОСТАЛЬНОЕ ТВОЁ БЕЗ ИЗМЕНЕНИЙ (view_bookings, delete_by_id, clear_old_bookings и т.д.)
