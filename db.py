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
    "autocommit": True
}

pool = None

async def init_db():
    global pool
    pool = await aiomysql.create_pool(**DB_CONFIG)

async def add_booking(name, date, time, service, phone):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO appointments (name, service, date, time, phone)
                    VALUES (%s, %s, %s, %s, %s)
                """, (name, service, date, time, phone))
        return True
    except Exception as e:
        print("Ошибка добавления:", e)
        return False

async def get_all_bookings():
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM appointments")
            return await cur.fetchall()
