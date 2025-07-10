# handlers.py
import re
import os
import urllib.parse
from datetime import datetime

import aiohttp
from aiogram import types, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import add_booking, get_all_bookings, delete_booking_by_id, save_draft, get_draft, clear_draft

class BookingForm(StatesGroup):
    name = State()
    service = State()
    date = State()
    time = State()
    phone = State()

services = [
    "Наращивание ресниц",
    "Ламинирование ресниц",
    "Ламинирование бровей",
    "Коррекция и окрашивание бровей",
    "Мусульманская коррекция",
]

def get_service_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=s, callback_data=f"svc_{i}")] for i, s in enumerate(services)]
    )

def is_valid_phone(phone):
    return bool(re.fullmatch(r"\+996\d{9}", phone))

async def send_to_whatsapp(name, date, time, service, phone):
    api_phone = os.getenv("WHATSAPP_PHONE")
    api_key = os.getenv("WHATSAPP_API_KEY")
    if not api_phone or not api_key:
        return False

    msg = f"🕵 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
    url = f"https://api.callmebot.com/whatsapp.php?phone={api_phone}&text={urllib.parse.quote(msg)}&apikey={api_key}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return resp.status == 200
    except:
        return False

async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await clear_draft(message.from_user.id)
    await message.answer("👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?")
    await state.set_state(BookingForm.name)

async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50 or not any(c.isalpha() for c in name):
        await message.answer("❌ Введите корректное имя.")
        return
    await save_draft(message.from_user.id, "name", name)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)

async def process_service(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("svc_", ""))
    if 0 <= idx < len(services):
        await save_draft(callback.from_user.id, "service", services[idx])
        await callback.message.answer("🗓 На какую дату записаться? (ГГГГ-ММ-ДД)")
        await state.set_state(BookingForm.date)
    await callback.answer()

async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d").date()
        if parsed < datetime.now().date():
            raise ValueError
    except:
        await message.answer("❌ Формат даты: 2025-07-10")
        return
    await save_draft(message.from_user.id, "date", date)
    await message.answer("🕒 Во сколько? (например, 14:30)")
    await state.set_state(BookingForm.time)

async def ask_phone(message: types.Message, state: FSMContext):
    time = message.text.strip()
    try:
        parsed = datetime.strptime(time, "%H:%M").time()
        if parsed.hour < 8 or parsed.hour > 21:
            raise ValueError
    except:
        await message.answer("❌ Формат времени: 14:30")
        return

    draft = await get_draft(message.from_user.id)
    bookings = await get_all_bookings()
    if any(b[2] == draft.get("date") and b[3] == time for b in bookings):
        await message.answer("❌ Это время уже занято!")
        return

    await save_draft(message.from_user.id, "time", time)
    await message.answer("📱 Введите номер телефона (например, +996123456789):")
    await state.set_state(BookingForm.phone)

async def validate_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not is_valid_phone(phone):
        await message.answer("❌ Неверный формат номера. Пример: +996123456789")
        return

    await save_draft(message.from_user.id, "phone", phone)
    data = await get_draft(message.from_user.id)
    required = ["name", "service", "date", "time", "phone"]
    if not all(k in data and data[k] for k in required):
        await message.answer("❌ Ошибка: недостаточно данных. Попробуйте заново /start")
        await state.clear()
        return

    if not await add_booking(data["name"], data["date"], data["time"], data["service"], data["phone"]):
        await message.answer("❌ Ошибка при сохранении. Попробуйте позже.")
        return

    await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], data["phone"])

    await message.answer(
        f"✅ Запись подтверждена!\n\nИмя: {data['name']}\nУслуга: {data['service']}\nДата: {data['date']}\nВремя: {data['time']}\nТелефон: {data['phone']}"
    )
    await state.clear()
    await clear_draft(message.from_user.id)

async def view_bookings(message: types.Message):
    admin = os.getenv("ADMIN_USER_ID", "0")
    if str(message.from_user.id) != admin:
        await message.answer("❌ Нет доступа.")
        return

    bookings = await get_all_bookings()
    if not bookings:
        await message.answer("📓 Нет записей.")
        return

    text = "\n\n".join(
        f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\nТелефон: {b[5]}" for b in bookings
    )
    await message.answer(f"📓 Все записи:\n\n{text}")

async def delete_by_id(message: types.Message):
    admin = os.getenv("ADMIN_USER_ID", "0")
    if str(message.from_user.id) != admin:
        await message.answer("❌ Нет доступа.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("⚠ Используй: /delete <ID>")
        return

    bid = int(parts[1])
    if await delete_booking_by_id(bid):
        await message.answer(f"✅ Удалено: {bid}")
    else:
        await message.answer("❌ Запись не найдена.")

def register_handlers(dp: Dispatcher):
    dp.message.register(start, CommandStart())
    dp.message.register(ask_service, BookingForm.name)
    dp.callback_query.register(process_service, lambda c: c.data.startswith("svc_"))
    dp.message.register(ask_time, BookingForm.date)
    dp.message.register(ask_phone, BookingForm.time)
    dp.message.register(validate_phone, BookingForm.phone)
    dp.message.register(view_bookings, Command("viewbookings"))
    dp.message.register(delete_by_id, Command("delete"))