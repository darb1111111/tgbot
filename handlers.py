import re
import os
import urllib.parse
from datetime import datetime, timedelta

import aiohttp
from aiogram import types, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from db import add_booking, get_all_bookings, delete_booking_by_id

# ────────────────────────
# FSM состояния
# ────────────────────────
class BookingForm(StatesGroup):
    name = State()
    service = State()
    date = State()
    time = State()
    phone = State()

# ────────────────────────
# Услуги
# ────────────────────────
services = [
    "Наращивание ресниц",
    "Ламинирование ресниц",
    "Ламинирование бровей",
    "Коррекция и окрашивание бровей",
    "Мусульманская коррекция",
]

def get_service_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=service, callback_data=f"svc_{i}")]
            for i, service in enumerate(services)
        ]
    )

def is_valid_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\+996\d{9}", phone))

# ────────────────────────
# WhatsApp уведомление
# ────────────────────────
async def send_to_whatsapp(name, date, time, service, phone) -> bool:
    api_phone = os.getenv("WHATSAPP_PHONE")
    api_key = os.getenv("WHATSAPP_API_KEY")
    if not api_phone or not api_key:
        print("❌ WhatsApp API не настроен")
        return False

    text = (
        f"🕵️ Новая запись:\n"
        f"Имя: {name}\n"
        f"Услуга: {service}\n"
        f"Дата: {date}\n"
        f"Время: {time}\n"
        f"Телефон: {phone}"
    )
    encoded = urllib.parse.quote(text)
    url = f"https://api.callmebot.com/whatsapp.php?phone={api_phone}&text={encoded}&apikey={api_key}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"❌ Ошибка отправки WhatsApp: {e}")
        return False

# ────────────────────────
# Хендлеры
# ────────────────────────
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BookingForm.name)
    await message.answer("👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?", reply_markup=ReplyKeyboardRemove())

async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50 or not any(c.isalpha() for c in name):
        await message.answer("❌ Введите корректное имя (только буквы, до 50 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(BookingForm.service)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())

# Убираем хендлер игнорирования текста на service — пусть бот просто не реагирует на текст в этом состоянии.

async def process_service(callback: types.CallbackQuery, state: FSMContext):
    try:
        index = int(callback.data.replace("svc_", ""))
        if not (0 <= index < len(services)):
            await callback.message.answer("❌ Неверная услуга.")
            await callback.answer()
            return
        await state.update_data(service=services[index])
        await state.set_state(BookingForm.date)
        await callback.message.edit_reply_markup(reply_markup=None)  # убираем inline клавиатуру после выбора
        await callback.message.answer("🗓 На какую дату записаться? (Формат: ГГГГ-ММ-ДД)")
        await callback.answer()
    except Exception as e:
        print(f"❌ Ошибка process_service: {e}")
        await callback.answer()

async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d")
        if parsed.date() < datetime.now().date():
            await message.answer("❌ Дата не может быть в прошлом. Введите снова:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД.")
        return

    await state.update_data(date=date)
    await state.set_state(BookingForm.time)
    await message.answer("🕒 Во сколько? (Формат: ЧЧ:ММ, например, 14:30)")

async def ask_phone(message: types.Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        if not (8 <= time_obj.hour <= 21):
            await message.answer("❌ Запись доступна с 08:00 до 21:00. Введите снова:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите ЧЧ:ММ.")
        return

    data = await state.get_data()
    date = data.get("date")

    try:
        new_start = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
        new_end = new_start + timedelta(hours=2)
        bookings = await get_all_bookings()

        for b in bookings:
            _, _, b_date, b_time, *_ = b
            exist_start = datetime.strptime(f"{b_date} {str(b_time)[:5]}", "%Y-%m-%d %H:%M")
            exist_end = exist_start + timedelta(hours=2)

            if new_start < exist_end and exist_start < new_end:
                await message.answer(f"❌ Пересечение с записью: {b_date} {str(b_time)[:5]} - выберите другое время.")
                return
    except Exception as e:
        print(f"❌ Ошибка проверки времени: {e}")
        await message.answer("⚠️ Внутренняя ошибка. Попробуйте заново /start")
        await state.clear()
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
    try:
        success = await add_booking(
            data["name"], data["service"], data["date"], data["time"], phone
        )
        if not success:
            await message.answer("❌ Не удалось сохранить запись. Попробуйте позже.")
            await state.clear()
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
    except Exception as e:
        print(f"❌ Ошибка при завершении записи: {e}")
        await message.answer("⚠️ Не удалось завершить запись. Попробуйте позже.")
    finally:
        await state.clear()

async def view_bookings(message: types.Message):
    admin_id = os.getenv("ADMIN_USER_ID", "0")
    if str(message.from_user.id) != admin_id:
        await message.answer("❌ Нет доступа.")
        return

    bookings = await get_all_bookings()
    if not bookings:
        await message.answer("📓 Нет записей.")
        return

    text = "\n\n".join(
        f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\nТелефон: {b[5]}"
        for b in bookings
    )
    await message.answer(f"📓 Все записи:\n\n{text}")

async def delete_by_id(message: types.Message):
    admin_id = os.getenv("ADMIN_USER_ID", "0")
    if str(message.from_user.id) != admin_id:
        await message.answer("❌ Нет доступа.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("⚠ Формат: /delete <ID>")
        return

    booking_id = int(parts[1])
    if await delete_booking_by_id(booking_id):
        await message.answer(f"✅ Запись {booking_id} удалена.")
    else:
        await message.answer("❌ Запись не найдена.")

# ────────────────────────
# Регистрация хендлеров
# ────────────────────────
def register_handlers(dp: Dispatcher):
    dp.message.register(start, CommandStart())
    dp.message.register(ask_service, BookingForm.name)
    dp.callback_query.register(process_service, lambda c: c.data.startswith("svc_"))
    # Убираем регистрацию ignore_text_on_service, чтобы не мешать корректной работе
    dp.message.register(ask_time, BookingForm.date)
    dp.message.register(ask_phone, BookingForm.time)
    dp.message.register(validate_phone, BookingForm.phone)
    dp.message.register(view_bookings, Command("viewbookings"))
    dp.message.register(delete_by_id, Command("delete"))