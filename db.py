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
    c.execute("INSERT INTO bookings (name, date, time, service, phone) VALUES (?, ?, ?, ?, ?)",
            (name, date, time, service, phone))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("SELECT id, name, date, time, service, phone FROM bookings ORDER BY date, time")
    bookings = c.fetchall()
    conn.close()
    return bookings
