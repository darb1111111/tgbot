import asyncio
import aiomysql

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "your_user",
    "password": "your_password",
    "db": "your_database",
}

async def init_db():
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50),
                date DATE,
                time TIME,
                service VARCHAR(100),
                phone VARCHAR(20)
            )
        """)
    await conn.commit()
    conn.close()

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
