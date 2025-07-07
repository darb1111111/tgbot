import asyncio
import logging
import os
from datetime import datetime, timedelta
import pytz
import urllib.parse
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import aiohttp

# Предполагается, что эти модули определены в другом файле
from keep_alive import app
from db import init_db, close_db, add_booking, get_all_bookings, delete_booking_by_id

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования (без записи в файл для совместимости с Pyodide)
logging.basicConfig(
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

async def send_to_whatsapp(name, date, time, service, phone):
    api_phone = os.getenv("WHATSAPP_PHONE")
    apikey = os.getenv("API_KEY")
    if not api_phone or not apikey:
        logging.error("Отсутствуют WHATSAPP_PHONE или API_KEY")
        return
    message = f"📅 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
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

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?")
    await state.set_state(BookingForm.name)

@dp.message(Command("viewbookings"))
async def view_bookings(message: types.Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет доступа к просмотру базы данных!")
        return
    try:
        bookings = await get_all_bookings()
        if not bookings:
            await message.answer("📓 Нет записей.")
            return
        text = "📓 Все записи:\n\n"
        for b in bookings:
            text += f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\nТелефон: {b[5]}\n\n"
        await message.answer(text)
    except Exception as e:
        logging.error(f"Ошибка при получении записей: {e}")
        await message.answer("⚠️ Ошибка при загрузке записей. Попробуйте позже.")

@dp.message(Command("delete"))
async def delete_by_id(message: types.Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет доступа к этой команде!")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("⚠️ Использование: /delete <ID>\nПример: /delete 12")
        return
    booking_id = int(parts[1])
    try:
        success = await delete_booking_by_id(booking_id)
        if success:
            await message.answer(f"✅ Запись с ID {booking_id} успешно удалена.")
        else:
            await message.answer(f"❌ Запись с ID {booking_id} не найдена.")
    except Exception as e:
        logging.error(f"Ошибка при удалении записи ID {booking_id}: {e}")
        await message.answer("⚠️ Ошибка при удалении записи. Попробуйте позже.")

@dp.message(BookingForm.name)
async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("❌ Введите корректное имя (не более 50 символов).")
        return
    await state.update_data(name=name)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)

@dp.callback_query(lambda c: c.data.startswith("svc_"))
async def process_service(callback: types.CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.replace("svc_", ""))
        if idx < 0 or idx >= len(services):
            await callback.message.answer("❌ Неверный выбор услуги!")
            return
        await state.update_data(service=services[idx])
        await callback.message.answer("🗓 На какую дату записаться? (например, 2025-06-01)")
        await state.set_state(BookingForm.date)
        await callback.answer()
    except ValueError:
        logging.error(f"Неверный формат callback_data: {callback.data}")
        await callback.message.answer("⚠️ Ошибка при выборе услуги. Попробуйте снова.")
        await callback.answer()

@dp.message(BookingForm.date)
async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    timezone = pytz.timezone(TIMEZONE)
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        if parsed_date.date() < datetime.now(timezone).date():
            await message.answer("❌ Нельзя записаться на прошедшую дату!")
            return
    except ValueError:
        await message.answer("❌ Неверный формат даты! Введите, например, 2025-06-01.")
        return
    await state.update_data(date=date)
    await message.answer("🕒 Во сколько? (например, 14:30)")
    await state.set_state(BookingForm.time)

async def check_time_availability(date: str, time: str) -> bool:
    try:
        new_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        timezone = pytz.timezone(TIMEZONE)
        new_time = timezone.localize(new_time)
    except ValueError:
        logging.warning(f"Неверный формат даты или времени: {date} {time}")
        return False

    bookings = await get_all_bookings()
    logging.debug(f"[DEBUG] Все записи из БД: {bookings}")

    for b in bookings:
        try:
            booked_time = datetime.strptime(f"{b[2]} {b[3]}", "%Y-%m-%d %H:%M")
            booked_time = timezone.localize(booked_time)
            # Проверка 2-часового интервала
            time_diff = abs((new_time - booked_time).total_seconds()) / 3600
            if b[2] == date and time_diff < 2:
                logging.info(f"Время {date} {time} недоступно (конфликт с {b[2]} {b[3]})")
                return False
        except Exception as e:
            logging.error(f"Ошибка при обработке записи {b}: {e}")
            return False
    return True

@dp.message(BookingForm.time)
async def ask_phone(message: types.Message, state: FSMContext):
    time = message.text.strip()
    data = await state.get_data()
    date = data.get("date")
    if not date:
        await message.answer("❌ Дата не найдена. Пожалуйста, начните сначала.")
        logging.warning("Дата отсутствует в состоянии.")
        await state.clear()
        return

    try:
        datetime.strptime(time, "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат времени! Введите, например, 14:30.")
        return

    try:
        is_available = await check_time_availability(date, time)
        if not is_available:
            await message.answer("❌ Это время недоступно! Должно быть минимум 2 часа между записями. Попробуйте другое время.")
            return
    except Exception as e:
        logging.error(f"Ошибка при проверке доступности времени: {e}")
        await message.answer("⚠️ Произошла ошибка при проверке времени. Попробуйте другое время.")
        return

    await state.update_data(time=time)
    await message.answer("📱 Введите свой номер телефона (например, +996123456789):")
    await state.set_state(BookingForm.phone)

@dp.message(BookingForm.phone)
async def validate_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith('+') or len(phone) < 10 or not phone[1:].isdigit():
        await message.answer("❌ Неверный формат номера! Введите, например, +996123456789.")
        return
    try:
        data = await state.get_data()
        success = await add_booking(data["name"], data["date"], data["time"], data["service"], data["phone"])
        if not success:
            await message.answer("❌ Ошибка при сохранении записи. Попробуйте позже.")
            return
        await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], data["phone"])
        logging.info(f"Новая запись: {data['name']}, {data['service']}, {data['date']}, {data['time']}, {data['phone']}")
        await message.answer(
            f"✅ Запись подтверждена!\n\n"
            f"Имя: {data['name']}\n"
            f"Услуга: {data['service']}\n"
            f"Дата: {data['date']}\n"
            f"Время: {data['time']}\n"
            f"Телефон: {data['phone']}\n\n"
            f"Спасибо за запись! 💬"
        )
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при сохранении записи: {e}")
        await message.answer("f❌ Ошибка при сохранении: {e.__class__.__name__}: {e}")
        await state.clear()

async def clear_old_bookings():
    try:
        timezone = pytz.timezone(TIMEZONE)
        cutoff_date = datetime.now(timezone) - timedelta(days=2)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        from db import pool  # Предполагается, что pool определен в db.py
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM bookings WHERE date < %s", (cutoff_str,))
                await conn.commit()
        logging.info(f"Очистка записей старше {cutoff_str} выполнена.")
    except Exception as e:
        logging.error(f"Ошибка при очистке старых записей: {e}")

@dp.message(Command("clear"))
async def clear_old_records_command(message: types.Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет доступа к этой команде!")
        return
    try:
        await clear_old_bookings()
        await message.answer("✅ Старые записи успешно удалены.")
    except Exception as e:
        logging.error(f"Ошибка при выполнении команды /clear: {e}")
        await message.answer("⚠️ Ошибка при очистке записей. Попробуйте позже.")

async def run_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

async def main():
    await asyncio.sleep(2)  # Задержка для предотвращения скачков подключения
    try:
        await init_db()
        await run_web()
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())