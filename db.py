import aiomysql
import os
from dotenv import load_dotenv

load_dotenv()

def str_strip(value):
    return value.strip() if isinstance(value, str) else value

DB_CONFIG = {
    "host": str_strip(os.getenv("DB_HOST")),
    "port": int(str_strip(os.getenv("DB_PORT", "3306"))),
    "user": str_strip(os.getenv("DB_USER")),
    "password": str_strip(os.getenv("DB_PASSWORD")),
    "db": str_strip(os.getenv("DB_NAME")),
    "minsize": 1,
    "maxsize": 3,
}

# Проверка наличия всех обязательных параметров
for key, value in DB_CONFIG.items():
    if value in (None, ""):
        raise ValueError(f"❌ Переменная окружения '{key}' не задана или пуста!")

pool = None

async def init_db():
    global pool
    if pool is not None:
        pool.close()
        await pool.wait_closed()
        print("🔁 Предыдущий пул закрыт.")
    pool = await aiomysql.create_pool(**DB_CONFIG)
    print("✅ Пул подключений к базе данных создан.")

async def get_db_connection():
    global pool
    if pool is None:
        raise Exception("❌ Пул соединений не инициализирован. Сначала вызовите init_db()")
    return await pool.acquire()

async def add_booking(name, date, time, service, phone):
    global pool
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "INSERT INTO appointments (name, date, time, service, phone) VALUES (%s, %s, %s, %s, %s)",
                    (name, date, time, service, phone)
                )
                await conn.commit()
                return True
            except Exception as e:
                print("❌ Ошибка при сохранении:", e)
                return False

async def get_all_bookings():
    global pool
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM appointments")
            return await cur.fetchall()

async def delete_booking_by_id(booking_id: int):
    global pool
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("DELETE FROM appointments WHERE id = %s", (booking_id,))
            await conn.commit()
            return cursor.rowcount > 0  # True, если запись удалена

async def close_db():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        pool = None
        print("🔒 Подключение к базе данных закрыто.")
    else:
        print("ℹ Пул базы данных уже закрыт или не инициализирован.")
