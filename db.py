import aiomysql
import os
from dotenv import load_dotenv
from typing import Any

load_dotenv()

def str_strip(value) -> str | None:
    return value.strip() if isinstance(value, str) else None

DB_CONFIG = {
    "host": str_strip(os.getenv("DB_HOST", "localhost")),
    "port": int(str_strip(os.getenv("DB_PORT", "3306"))),
    "user": str_strip(os.getenv("DB_USER", "root")),
    "password": str_strip(os.getenv("DB_PASSWORD", "")),
    "db": str_strip(os.getenv("DB_NAME", "tgbot")),
    "minsize": 1,
    "maxsize": 10
}

pool = None

async def init_db() -> None:
    global pool
    if pool is not None:
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
                        date VARCHAR(10),
                        time VARCHAR(5),
                        service VARCHAR(100),
                        phone VARCHAR(15)
                    )
                """)
        print("База данных инициализирована")
    except Exception as e:
        print(f"Произошла ошибка при инициализации базы данных: {e}, конфигурация: {DB_CONFIG}")
        raise

async def close_db() -> None:
    global pool
    if pool is not None:
        await pool.close()
        await pool.wait_closed()
        print("Соединение с базой данных закрыто")

async def db_connection() -> Any:
    global pool
    if pool is None:
        raise Exception("База данных не инициализирована. Сначала вызовите init_db()")
    return await pool.acquire()

async def add_booking(name: str, date: str, time: str, service: str, phone: str) -> bool:
    global pool
    if pool is None:
        raise Exception("База данных не инициализирована")
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO appointments (name, date, time, service, phone) VALUES (%s, %s, %s, %s, %s)",
                    (name, date, time, service, phone)
                )
                await conn.commit()
            return True
    except Exception as e:
        print(f"Ошибка при добавлении записи: {e}")
        if 'conn' in locals():
            await conn.rollback()
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
        print(f"Ошибка при получении записей: {e}")
        return []

async def delete_booking_by_id(booking_id: int) -> bool:
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
        print(f"Ошибка при удалении записи ID {booking_id}: {e}")
        if 'conn' in locals():
            await conn.rollback()
        return False