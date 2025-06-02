import sqlite3
from pathlib import Path
import logging

db_path = Path(__file__).parent / 'appointments.db'

def init_db():
    try:
        with sqlite3.connect(db_path) as conn:
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
        logging.info(f"Database initialized at {db_path}")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

def add_booking(name, date, time, service, phone):
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO bookings (name, date, time, service, phone) VALUES (?, ?, ?, ?, ?)",
                (name, date, time, service, phone),
            )
            conn.commit()
            # Проверяем добавление
            c.execute("SELECT last_insert_rowid()")
            last_id = c.fetchone()[0]
            c.execute("SELECT * FROM bookings WHERE id = ?", (last_id,))
            record = c.fetchone()
            if record:
                logging.info(f"Booking added successfully: {record}")
            else:
                logging.error(f"Booking not found after insert!")
        return True
    except Exception as e:
        logging.error(f"Error adding booking: {e}")
        return False

def get_all_bookings():
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, date, time, service, phone FROM bookings ORDER BY date, time")
            return c.fetchall()
    except Exception as e:
        logging.error(f"Error fetching bookings: {e}")
        return []
