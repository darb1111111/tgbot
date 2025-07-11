import re
import os
import urllib.parse
from datetime import datetime, timedelta

import aiohttp
from aiogram import types, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import add_booking, get_all_bookings, delete_booking_by_id

# FSM States
class BookingForm(StatesGroup):
    name = State()
    service = State()
    date = State()
    time = State()
    phone = State()

# Services
services = [
    "Наращивание ресниц",
    "Ламинирование ресниц",
    "Ламинирование бровей",
    "Коррекция и окрашивание бровей",
    "Мусульманская коррекция",
]

# Utilities
def get_service_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=service, callback_data=f"svc_{idx}")]
            for idx, service in enumerate(services)
        ]
    )

def is_valid_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\+996\d{9}", phone))

async def send_to_whatsapp(name: str, date: str, time: str, service: str, phone: str) -> bool:
    api_phone = os.getenv("WHATSAPP_PHONE")
    api_key = os.getenv("WHATSAPP_API_KEY")
    if not api_phone or not api_key:
        print("Ошибка: WHATSAPP_PHONE или WHATSAPP_API_KEY не установлены")
        return False

    message = (
        f"🕵️ Новая запись:\n"
        f"Имя: {name}\n"
        f"Услуга: {service}\n"
        f"Дата: {date}\n"
        f"Время: {time}\n"
        f"Телефон: {phone}"
    )
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={api_phone}&text={encoded_message}&apikey={api_key}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"Ошибка WhatsApp API: {e}")
        return False

# Handlers
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BookingForm.name)
    await state.update_data(name=None, service=None, date=None, time=None)
    await message.answer(
        "👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50 or not any(c.isalpha() for c in name):
        await message.answer("❌ Введите корректное имя (только буквы, до 50 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(BookingForm.service)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())

async def process_service(callback: types.CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.replace("svc_", ""))
        if idx < 0 or idx >= len(services):
            await callback.message.answer("❌ Неверная услуга.")
            return
        await state.update_data(service=services[idx])
        await state.set_state(BookingForm.date)
        await callback.message.answer("🗓 На какую дату записаться? (Формат: ГГГГ-ММ-ДД, например, 2025-07-10)")
    finally:
        await callback.answer()

async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        if parsed_date.date() < datetime.now().date():
            await message.answer("❌ Дата не может быть в прошлом.")
            return
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД.")
        return

    await state.update_data(date=date)
    await state.set_state(BookingForm.time)
    await message.answer("🕒 Во сколько? (Формат: ЧЧ:ММ, например, 14:30)")

async def ask_phone(message: types.Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        parsed_time = datetime.strptime(time_str, "%H:%M").time()
        if not (8 <= parsed_time.hour <= 21):
            await message.answer("❌ Запись возможна с 08:00 до 21:00.")
            return
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ.")
        return

    data = await state.get_data()
    date = data.get("date")
    if not date:
        await state.clear()
        await message.answer("❌ Ошибка. Попробуйте сначала /start")
        return

    try:
        new_start = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
        new_end = new_start + timedelta(hours=2)

        bookings = await get_all_bookings()

        for b in bookings:
            booking_id, name, b_date, b_time, service, phone = b

            if b_date != date:
                continue

            # нормализуем b_time
            if hasattr(b_time, 'strftime'):
                b_time_str = b_time.strftime("%H:%M")
            else:
                b_time_str = str(b_time)[:5]

            exist_start = datetime.strptime(f"{b_date} {b_time_str}", "%Y-%m-%d %H:%M")
            exist_end = exist_start + timedelta(hours=2)

            if new_start < exist_end and exist_start < new_end:
                await message.answer(f"❌ Пересечение с другой записью в {b_time_str}. Выберите другое время.")
                return
    except Exception as e:
        print(f"Ошибка проверки: {e}")
        await message.answer("❌ Ошибка при проверке времени. Попробуйте позже.")
        return

    await state.update_data(time=time_str)
    await state.set_state(BookingForm.phone)
    await message.answer("📱 Введите номер телефона (Формат: +996123456789):")

async def validate_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not is_valid_phone(phone):
        await message.answer("❌ Неверный формат номера. Используйте +996 и 9 цифр.")
        return

    data = await state.get_data()
    missing = [f for f in ["name", "service", "date", "time"] if not data.get(f)]
    if missing:
        await state.clear()
        await message.answer(f"❌ Ошибка: отсутствуют данные ({', '.join(missing)}). Попробуйте заново /start")
        return

    if not await add_booking(data["name"], data["service"], data["date"], data["time"], phone):
        await message.answer("❌ Ошибка при сохранении записи. Попробуйте позже.")
        return

    await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], phone)

    await message.answer(
        f"✅ Запись подтверждена!\n\n"
        f"Имя: {data['name']}\n"
        f"Услуга: {data['service']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Телефон: {phone}"
    )
    await state.clear()

async def view_bookings(message: types.Message):
    admin_id = os.getenv("ADMIN_USER_ID", "0")
    if str(message.from_user.id) != admin_id:
        await message.answer("❌ Нет доступа. Только админ может просматривать записи.")
        return

    bookings = await get_all_bookings()
    if not bookings:
        await message.answer("📓 Нет активных записей.")
        return

    text = "\n\n".join(
        f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\nТелефон: {b[5]}"
        for b in bookings
    )
    await message.answer(f"📓 Все записи:\n\n{text}")

async def delete_by_id(message: types.Message):
    admin_id = os.getenv("ADMIN_USER_ID", "0")
    if str(message.from_user.id) != admin_id:
        await message.answer("❌ Нет доступа. Только админ может удалять записи.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("⚠ Формат команды: /delete <ID>")
        return

    booking_id = int(parts[1])
    if await delete_booking_by_id(booking_id):
        await message.answer(f"✅ Запись с ID {booking_id} удалена.")
    else:
        await message.answer("❌ Запись не найдена.")

# Register Handlers
def register_handlers(dp: Dispatcher):
    dp.message.register(start, CommandStart())
    dp.message.register(ask_service, BookingForm.name)
    dp.callback_query.register(process_service, lambda c: c.data.startswith("svc_"))
    dp.message.register(ask_time, BookingForm.date)
    dp.message.register(ask_phone, BookingForm.time)
    dp.message.register(validate_phone, BookingForm.phone)
    dp.message.register(view_bookings, Command("viewbookings"))
    dp.message.register(delete_by_id, Command("delete"))