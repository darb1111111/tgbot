import sqlite3

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

def add_booking(name, date, time, service):
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute("INSERT INTO bookings (name, date, time, service) VALUES (?, ?, ?, ?)", (name, date, time, service))
    conn.commit()
    conn.close()