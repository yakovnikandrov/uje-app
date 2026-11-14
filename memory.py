# memory.py
import sqlite3
import os
import time

if os.name != 'nt': 
    DB_NAME = "/data/uje_memory.db"
else:
    DB_NAME = "uje_memory.db"

def init_db():
    if not os.path.exists(os.path.dirname(DB_NAME)) and os.path.dirname(DB_NAME) != "":
        os.makedirs(os.path.dirname(DB_NAME))

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS profile (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pending (action TEXT, params TEXT, expires REAL)''')
        conn.commit()

def save_fact(key: str, value: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO profile (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value''', (key, value))
        conn.commit()

def get_all_facts() -> dict:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM profile')
        return {row[0]: row[1] for row in cursor.fetchall()}

def clear_all_facts():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM profile')
        cursor.execute('DELETE FROM pending')
        conn.commit()

def save_pending(action: str, params: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM pending')
        cursor.execute('INSERT INTO pending (action, params, expires) VALUES (?, ?, ?)', (action, params, time.time() + 600))
        conn.commit()

def get_pending():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT action, params, expires FROM pending')
        row = cursor.fetchone()
        if row and time.time() < row[2]:
            return {"action": row[0], "params": row[1]}
        return None

def clear_pending():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM pending')
        conn.commit()