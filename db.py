import asyncio
import aiomysql

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "bot_user",
    "password": "Bot2025$",
    "db": "telegram_bot_db",
}


async def init_db():
    global pool
    pool = await aiomysql.create_pool(
        host='localhost',
        port=3306,
        user='bot_user',
        password='Bot2025$',
        db='telegram_bot_db',
        autocommit=True
    )

async def add_booking(name, date, time, service, phone):
    try:
        conn = await aiomysql.connect(**DB_CONFIG)
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO bookings (name, date, time, service, phone)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, date, time, service, phone))
        await conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Ошибка добавления:", e)
        return False

async def get_all_bookings():
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM bookings")
        result = await cur.fetchall()
    conn.close()
    return result
