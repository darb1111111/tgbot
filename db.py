import sqlite3

def init_db():
    conn = sqlite3.connect('appointments.db')
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
    conn.close()

def add_booking(name, date, time, service, phone):
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    print(f"Попытка сохранить: name={name}, date={date}, time={time}, service={service}, phone={phone}")
    try:
        c.execute("INSERT INTO bookings (name, date, time, service, phone) VALUES (?, ?, ?, ?, ?)",
                  (name, date, time, service, phone))
        conn.commit()
        print("Запись успешно сохранена в базу данных")
    except sqlite3.Error as e:
        print(f"Ошибка при сохранении в базу данных: {e}")
    finally:
        conn.close()

def get_all_bookings():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("SELECT id, name, date, time, service, phone FROM bookings ORDER BY date, time")
    bookings = c.fetchall()
    conn.close()
    return bookings
