# handlers.py
import re
import os
import urllib.parse
from datetime import datetime

import aiohttp
from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command

from db import add_booking, get_all_bookings, delete_booking_by_id

# --- FSM States ---
class BookingForm(StatesGroup):
    name = State()
    service = State()
    date = State()
    time = State()
    phone = State()

# --- Services ---
services = [
    "Наращивание ресниц",
    "Ламинирование ресниц",
    "Ламинирование бровей",
    "Коррекция и окрашивание бровей",
    "Мусульманская коррекция",
]

# --- Utilities ---
def get_service_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=s, callback_data=f"svc_{i}")] for i, s in enumerate(services)]
    )

def is_valid_phone(phone: str) -> bool:
    return re.fullmatch(r"\+996\\d{9}", phone) is not None

async def send_to_whatsapp(name, date, time, service, phone):
    api_phone = os.getenv("WHATSAPP_PHONE")
    apikey = os.getenv("API_KEY")
    if not api_phone or not apikey:
        return
    message = f"🕵 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
    url = f"https://api.callmebot.com/whatsapp.php?phone={api_phone}&text={urllib.parse.quote(message)}&apikey={apikey}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    print(f"Ошибка WhatsApp API {resp.status}: {await resp.text()}")
    except Exception as e:
        print(f"Ошибка WhatsApp API: {e}")

# --- Handlers ---
async def start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?")
    await state.set_state(BookingForm.name)

async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50 or not any(c.isalpha() for c in name):
        return await message.answer("❌ Введите корректное имя.")
    await state.update_data(name=name)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)

async def process_service(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("svc_", ""))
    await state.update_data(service=services[idx])
    await callback.message.answer("🗓 На какую дату записаться? (ГГГГ-ММ-ДД)")
    await state.set_state(BookingForm.date)
    await callback.answer()

async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        if parsed_date.date() < datetime.now().date():
            return await message.answer("❌ Дата в прошлом.")
    except ValueError:
        return await message.answer("❌ Формат: 2025-07-10")
    await state.update_data(date=date)
    await message.answer("🕒 Во сколько? (например, 14:30)")
    await state.set_state(BookingForm.time)

async def ask_phone(message: types.Message, state: FSMContext):
    time = message.text.strip()
    try:
        parsed_time = datetime.strptime(time, "%H:%M").time()
        if parsed_time.hour < 8 or parsed_time.hour > 21:
            return await message.answer("❌ Запись с 08:00 до 21:00.")
    except ValueError:
        return await message.answer("❌ Формат: 14:30")
    data = await state.get_data()
    bookings = await get_all_bookings()
    if any(b[2] == data["date"] and b[3] == time for b in bookings):
        return await message.answer("❌ Это время занято!")
    await state.update_data(time=time)
    await message.answer("📱 Введите телефон (например, +996123456789):")
    await state.set_state(BookingForm.phone)

async def validate_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not is_valid_phone(phone):
        return await message.answer("❌ Формат: +996123456789")
    data = await state.update_data(phone=phone)
    data = await state.get_data()
    saved = await add_booking(data["name"], data["date"], data["time"], data["service"], phone)
    if not saved:
        return await message.answer("❌ Ошибка при сохранении.")
    await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], phone)
    await message.answer(
        f"✅ Запись подтверждена!\nИмя: {data['name']}\nУслуга: {data['service']}\nДата: {data['date']}\n"
        f"Время: {data['time']}\nТелефон: {phone}"
    )
    await state.clear()

async def view_bookings(message: types.Message):
    if message.from_user.id != int(os.getenv("ADMIN_USER_ID", "0")):
        return await message.answer("❌ Нет доступа.")
    bookings = await get_all_bookings()
    if not bookings:
        return await message.answer("📓 Нет записей.")
    text = "\n\n".join(
        f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\nТелефон: {b[5]}"
        for b in bookings
    )
    await message.answer(f"📓 Все записи:\n\n{text}")

async def delete_by_id(message: types.Message):
    if message.from_user.id != int(os.getenv("ADMIN_USER_ID", "0")):
        return await message.answer("❌ Нет доступа.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("⚠ /delete <ID>")
    booking_id = int(parts[1])
    if await delete_booking_by_id(booking_id):
        await message.answer(f"✅ Удалено: {booking_id}")
    else:
        await message.answer("❌ Запись не найдена.")

# --- Регистрация всех хендлеров ---
def register_handlers(dp: Dispatcher):
    dp.message.register(start, CommandStart())
    dp.message.register(ask_service, BookingForm.name)
    dp.callback_query.register(process_service, lambda c: c.data.startswith("svc_"))
    dp.message.register(ask_time, BookingForm.date)
    dp.message.register(ask_phone, BookingForm.time)
    dp.message.register(validate_phone, BookingForm.phone)
    dp.message.register(view_bookings, Command("viewbookings"))
    dp.message.register(delete_by_id, Command("delete"))