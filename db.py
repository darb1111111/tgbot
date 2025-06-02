import sqlite3
from pathlib import Path
import logging
import time

db_path = Path(__file__).parent / 'appointments.db'

def init_db():
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("PRAGMA journal_mode=WAL")  # Для уменьшения блокировок
            c.execute('''CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                service TEXT NOT NULL,
                phone TEXT NOT NULL
            )''')
            conn.commit()
        logging.info(f"Database initialized at {db_path}")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

def add_booking(name, date, time, service, phone, retry=3):
    for attempt in range(retry):
        try:
            with sqlite3.connect(db_path, timeout=10) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO bookings (name, date, time, service, phone) VALUES (?, ?, ?, ?, ?)",
                          (name, date, time, service, phone))
                conn.commit()
                return True
        except sqlite3.OperationalError as e:
            logging.warning(f"Database busy, retrying... ({attempt+1}/{retry})")
            time.sleep(1)
        except Exception as e:
            logging.error(f"Error adding booking: {e}")
            break
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
