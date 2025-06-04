import aiomysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME"),
    "minsize": 1,
    "maxsize": 3,
}

pool = None

async def init_db():
    global pool
    if pool is not None:
        pool.close()
        await pool.wait_closed()
        print("Предыдущий пул закрыт.")
    pool = await aiomysql.create_pool(**DB_CONFIG)
    print("Пул подключений создан.")

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
                print("Ошибка при сохранении:", e)
                return False

async def get_all_bookings():
    global pool
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM appointments")
            return await cur.fetchall()

async def close_db():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        pool = None
        print("База данных закрыта.")
    else:
        print("База данных уже закрыта или не инициализирована.")