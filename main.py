import asyncio
import aiohttp
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
import urllib.parse
from datetime import datetime
import pytz  # Для работы с часовыми поясами
import logging  # Для логирования
from keep_alive import app  # Предполагается, что keep_alive.py существует и корректен

# Настройка логирования
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Услуги
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

def init_db():
    with sqlite3.connect('appointments.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            time TEXT,
            service TEXT,
            phone TEXT
        )''')
        conn.commit()
    logging.info("База данных инициализирована")

def add_booking(name, date, time, service, phone):
    with sqlite3.connect('appointments.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO bookings (name, date, time, service, phone) VALUES (?, ?, ?, ?, ?)", 
                  (name, date, time, service, phone))
        conn.commit()
    logging.info(f"Добавлена запись: {name}, {service}, {date}, {time}, {phone}")

def check_time_availability(date, time):
    with sqlite3.connect('appointments.db') as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM bookings WHERE date = ? AND time = ?", (date, time))
        count = c.fetchone()[0]
    return count == 0

def get_all_bookings():
    with sqlite3.connect('appointments.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, date, time, service, phone FROM bookings ORDER BY date, time")
        bookings = c.fetchall()
    return bookings

async def send_to_whatsapp(name, date, time, service, phone):
    phone_number = config.ADMIN_PHONE
    apikey = config.apikey
    message = f"📅 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_message}&apikey={apikey}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    logging.info(f"Успешно отправлено в WhatsApp: {message}")
                    return True
                else:
                    logging.error(f"Ошибка отправки в WhatsApp, код {resp.status}: {response_text}")
                    return False
        except Exception as e:
            logging.error(f"Исключение при отправке в WhatsApp: {e}")
            return False

async def send_to_telegram_fallback(name, date, time, service, phone):
    try:
        message = f"📅 Новая запись (резерв):\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
        await bot.send_message(chat_id=config.ADMIN_USER_ID, text=message)
        logging.info(f"Резервное сообщение отправлено в Telegram: {message}")
    except Exception as e:
        logging.error(f"Исключение при отправке резервного сообщения в Telegram: {e}")

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?")
    await state.set_state(BookingForm.name)
    logging.info(f"Пользователь {message.from_user.id} начал процесс записи")

@dp.message(Command("viewbookings"))
async def view_bookings(message: types.Message):
    allowed_user_id = config.ADMIN_USER_ID
    if message.from_user.id != allowed_user_id:
        await message.answer("❌ У вас нет доступа к просмотру базы данных!")
        logging.warning(f"Пользователь {message.from_user.id} пытался получить доступ к записям")
        return
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("📅 Нет записей.")
        logging.info("Запрошены записи, база пуста")
        return
    text = "📅 Все записи:\n\n"
    for b in bookings:
        text += f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\nТелефон: {b[5]}\n\n"
    await message.answer(text)
    logging.info(f"Пользователь {message.from_user.id} просмотрел записи")

@dp.message(BookingForm.name)
async def ask_service(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("❌ Пожалуйста, введите корректное имя (не пустое, до 50 символов).")
        logging.warning(f"Некорректное имя: {message.text}")
        return
    await state.update_data(name=name)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)
    logging.info(f"Пользователь {message.from_user.id} ввел имя: {name}")

@dp.callback_query(lambda c: c.data.startswith("svc_"))
async def process_service(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("svc_", ""))
    await state.update_data(service=services[idx])
    await callback.message.answer("📆 На какую дату записаться? (например, 2025-06-01)")
    await state.set_state(BookingForm.date)
    await callback.answer()
    logging.info(f"Пользователь {callback.from_user.id} выбрал услугу: {services[idx]}")

@dp.message(BookingForm.date)
async def ask_time(message: types.Message, state: FSMContext):
    date = message.text.strip()
    timezone = pytz.timezone(config.TIMEZONE)  # Часовой пояс из config
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        local_date = timezone.localize(parsed_date)
        if local_date.date() < datetime.now(timezone).date():
            await message.answer("❌ Нельзя записаться на прошедшую дату! Введите дату, например, 2025-06-01.")
            logging.warning(f"Попытка записи на прошедшую дату: {date}")
            return
    except ValueError:
        await message.answer("❌ Неверный формат даты! Введите, например, 2025-06-01.")
        logging.warning(f"Некорректный формат даты: {message.text}")
        return
    await state.update_data(date=date)
    await message.answer("🕓 Во сколько? (например, 14:30)")
    await state.set_state(BookingForm.time)
    logging.info(f"Пользователь {message.from_user.id} выбрал дату: {date}")

@dp.message(BookingForm.time)
async def ask_phone(message: types.Message, state: FSMContext):
    time = message.text.strip()
    try:
        datetime.strptime(time, "%H:%M")
        data = await state.get_data()
        if not check_time_availability(data.get("date"), time):
            await message.answer("❌ Это время уже занято! Выберите другое, например, 14:30.")
            logging.warning(f"Время занято: {data.get('date')} {time}")
            return
    except ValueError:
        await message.answer("❌ Неверный формат времени! Введите, например, 14:30.")
        logging.warning(f"Некорректный формат времени: {message.text}")
        return
    await state.update_data(time=time)
    await message.answer("📱 Введите свой номер телефона для связи (например, +996123456789):")
    await state.set_state(BookingForm.phone)
    logging.info(f"Пользователь {message.from_user.id} выбрал время: {time}")

@dp.message(BookingForm.phone)
async def confirm(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith('+') or len(phone) < 10 or not phone[1:].isdigit():
        await message.answer("❌ Неверный формат номера! Введите, например, +996123456789.")
        logging.warning(f"Некорректный номер телефона: {message.text}")
        return
    await state.update_data(phone=phone)
    data = await state.get_data()
    add_booking(data["name"], data["date"], data["time"], data["service"], data["phone"])
    # Отправка в WhatsApp и резервное уведомление
    whatsapp_success = await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], data["phone"])
    if not whatsapp_success:
        await send_to_telegram_fallback(data["name"], data["date"], data["time"], data["service"], data["phone"])
    await message.answer(
        f"✅ Запись подтверждена!\n\n"
        f"Имя: {data['name']}\n"
        f"Услуга: {data['service']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"Спасибо за запись! Мы свяжемся с вами для уточнения деталей. 💬"
    )
    logging.info(f"Запись подтверждена для {message.from_user.id}: {data}")
    await state.clear()

# 🌐 Запуск веб-сервера
async def run_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logging.info("Веб-сервер запущен на http://0.0.0.0:8080")

# 🚀 Запуск бота и веба
async def main():
    init_db()
    await asyncio.gather(run_web(), dp.start_polling(bot, skip_updates=True))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Ошибка при запуске: {e}")