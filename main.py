import asyncio
import aiohttp
import sqlite3
from aiohttp import web  # <-- обязательно!
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
import urllib.parse
from keep_alive import app  # <-- импортируем aiohttp-приложение

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
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        date TEXT,
        time TEXT,
        service TEXT
        phone TEXT
    )''')
    conn.commit()
    conn.close()

def add_booking(name, date, time, service):
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("INSERT INTO bookings (name, date, time, service) VALUES (?, ?, ?, ?)", (name, date, time, service))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("SELECT id, name, date, time, service FROM bookings ORDER BY date, time")
    bookings = c.fetchall()
    conn.close()
    return bookings

async def send_to_whatsapp(name, date, time, service):
    phone = "996709111301"
    apikey = config.apikey
    message = f"📅 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}"
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_message}&apikey={apikey}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    print(f"✅ Успешно отправлено в WhatsApp:\n{message}")
                else:
                    print(f"❌ Ошибка {resp.status}\n{response_text}")
        except Exception as e:
            print(f"❌ Исключение при отправке в WhatsApp: {e}")

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Я бот для онлайн-записи.\nКак тебя зовут?")
    await state.set_state(BookingForm.name)

@dp.message(Command("viewbookings"))
async def view_bookings(message: types.Message):
    allowed_user_id = 7046147843
    if message.from_user.id != allowed_user_id:
        await message.answer("❌ У вас нет доступа к просмотру базы данных!")
        return
    bookings = get_all_bookings()
    if not bookings:
        await message.answer("📅 Нет записей.")
        return
    text = "📅 Все записи:\n\n"
    for b in bookings:
        text += f"ID: {b[0]}\nИмя: {b[1]}\nУслуга: {b[4]}\nДата: {b[2]}\nВремя: {b[3]}\n\n"
    await message.answer(text)

@dp.message(BookingForm.name)
async def ask_service(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("💅 Какую услугу выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)

@dp.callback_query(lambda c: c.data.startswith("svc_"))
async def process_service(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("svc_", ""))
    await state.update_data(service=services[idx])
    await callback.message.answer("📆 На какую дату записаться? (например, 2025-06-01)")
    await state.set_state(BookingForm.date)
    await callback.answer()

@dp.message(BookingForm.date)
async def ask_time(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("🕓 Во сколько? (например, 14:30)")
    await state.set_state(BookingForm.time)

@dp.message(BookingForm.time)
async def ask_phone(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("📱 Введите свой номер телефона для связи:")
    await state.set_state(BookingForm.phone)

@dp.message(BookingForm.phone)
async def confirm(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    add_booking(data["name"], data["date"], data["time"], data["service"], data["phone"])
    await send_to_whatsapp(data["name"], data["date"], data["time"], data["service"], data["phone"])
    await message.answer(
        f"✅ Запись подтверждена!\n\n"
        f"Имя: {data['name']}\n"
        f"Услуга: {data['service']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"Спасибо за запись! Мы свяжемся с вами для уточнения деталей. 💬"
    )
    await state.clear()

# 🌐 Запуск веб-сервера
async def run_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌍 Веб-сервер доступен на http://0.0.0.0:8080")

# 🚀 Запуск бота и веба
async def main():
    init_db()
    await asyncio.gather(run_web(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main()) 