
import asyncio
import aiohttp
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
import urllib.parse

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

# Инлайн-клавиатура для услуг
def get_service_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s, callback_data=f"svc_{i}")] for i, s in enumerate(services)
    ])
    return keyboard

# Состояния
class BookingForm(StatesGroup):
    name = State()
    service = State()
    date = State()
    time = State()

# Инициализация БД
def init_db():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        date TEXT,
        time TEXT,
        service TEXT
    )''')
    conn.commit()
    conn.close()

# Добавление записи в БД
def add_booking(name, date, time, service):
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("INSERT INTO bookings (name, date, time, service) VALUES (?, ?, ?, ?)", (name, date, time, service))
    conn.commit()
    conn.close()

# Получение всех записей из БД
def get_all_bookings():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("SELECT id, name, date, time, service FROM bookings ORDER BY date, time")
    bookings = c.fetchall()
    conn.close()
    return bookings


async def send_to_whatsapp(name, date, time, service):
    phone = "996709111301"  
    apikey = config.apikey  # Ваш API ключ CallMeBot
    message = f"📅 Новая запись:\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}"
    encoded_message = urllib.parse.quote(message)  # Корректное кодирование URL
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_message}&apikey={apikey}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    print(f"✅ Сообщение успешно отправлено в WhatsApp: {message}")
                else:
                    print(f"❌ Ошибка отправки в WhatsApp: Статус {resp.status}")
                    print(f"Ответ сервера: {response_text}")
                    print(f"URL запроса: {url}")
        except Exception as e:
            print(f"❌ Исключение при отправке в WhatsApp: {e}")
            print(f"URL запроса: {url}")


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
        await message.answer("📅 Нет записей в базе данных.")
        return
    response = "📅 Все записи:\n\n"
    for booking in bookings:
        id, name, date, time, service = booking
        response += f"ID: {id}\nИмя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\n\n"
    await message.answer(response)

# Имя -> Услуга
@dp.message(BookingForm.name)
async def ask_service(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("💅 Какую услугу хотите выбрать?", reply_markup=get_service_keyboard())
    await state.set_state(BookingForm.service)

# Обработка выбора услуги
@dp.callback_query(lambda c: c.data.startswith("svc_"))
async def process_service(callback: types.CallbackQuery, state: FSMContext):
    service_index = int(callback.data.replace("svc_", ""))
    service = services[service_index]  # Получаем полное название услуги по индексу
    await state.update_data(service=service)
    await callback.message.answer("На какую дату хотите записаться? (например, 2025-06-01)")
    await state.set_state(BookingForm.date)
    await callback.answer()

# Дата -> Время
@dp.message(BookingForm.date)
async def ask_time(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("На какое время? (например, 14:30)")
    await state.set_state(BookingForm.time)

# Время -> Подтверждение
@dp.message(BookingForm.time)
async def confirm(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    data = await state.get_data()
    name = data["name"]
    date = data["date"]
    time = data["time"]
    service = data["service"]

    # Сохраняем в БД
    add_booking(name, date, time, service)

    # Отправляем в WhatsApp
    await send_to_whatsapp(name, date, time, service)

    await message.answer(
        f"Запись подтверждена!\n\n"
        f"Имя: {name}\nУслуга: {service}\nДата: {date}\nВремя: {time}\n\n"
        f"Спасибо за запись!"
    )
    await state.clear()

# Запуск бота
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    from keep_alive import keep_alive
    keep_alive()
    asyncio.run(main())