import aiomysql
import os
from dotenv import load_dotenv

load_dotenv()

def str_strip(value):
    return value.strip() if isinstance(value, str) else None

DB_CONFIG = {
    "host": str_strip(os.getenv("DB_HOST", "localhost")),
    "port": int(str_strip(os.getenv("DB_PORT", "3306"))),
    "user": str_strip(os.getenv("DB_USER", "root")),
    "password": str_strip(os.getenv("DB_PASSWORD", "")),
    "db": str_strip(os.getenv("DB_NAME", "tgbot")),
    "minsize": 1,
    "maxsize": 2
}

pool = None

async def init_db():
    global pool
    if pool:
        await pool.close()
        await pool.wait_closed()

    try:
        pool = await aiomysql.create_pool(**DB_CONFIG)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS appointments (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(50),
                        service VARCHAR(100),
                        date VARCHAR(10),
                        time VARCHAR(5),
                        phone VARCHAR(15)
                    )
                """)
                print("✅ База данных инициализирована.")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {type(e)._name_}: {e}")
        raise

async def close_db():
    global pool
    if pool:
        await pool.close()
        await pool.wait_closed()
        print("✅ Соединение с БД закрыто.")

async def add_booking(name, service, date, time, phone):
    global pool
    if pool is None:
        raise RuntimeError("БД не инициализирована")

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO appointments (name, service, date, time, phone) VALUES (%s, %s, %s, %s, %s)",
                    (name, service, date, time, phone)
                )
                await conn.commit()
                return True
    except Exception as e:
        print(f"❌ Ошибка при добавлении записи: {type(e)._name_}: {e}")
        print(f"🔍 Параметры: name={name}, service={service}, date={date}, time={time}, phone={phone}")
        return False

async def get_all_bookings():
    global pool
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT id, name, date, time, service, phone FROM appointments")
                return await cur.fetchall()
    except Exception as e:
        print(f"❌ Ошибка при получении записей: {type(e)._name_}: {e}")
        return []

async def delete_booking_by_id(booking_id):
    global pool
    if pool is None:
        return False

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM appointments WHERE id = %s", (booking_id,))
                await conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Ошибка при удалении записи: {type(e)._name_}: {e}")
        return False