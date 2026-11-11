# memory.py
import sqlite3
import os

# Умный выбор пути:
# Если это Linux (Amvera) - используем /data/ (там база сохраняется навсегда)
# Если это Windows (твой компьютер) - используем обычный файл в папке проекта
if os.name != 'nt': 
    DB_NAME = "/data/uje_memory.db"
else:
    DB_NAME = "uje_memory.db"

def init_db():
    """Создает таблицу для хранения фактов о пользователе"""
    # Создаем папку /data, если ее нет (для Amvera)
    if not os.path.exists(os.path.dirname(DB_NAME)) and os.path.dirname(DB_NAME) != "":
        os.makedirs(os.path.dirname(DB_NAME))

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()

def save_fact(key: str, value: str):
    """Сохраняет или обновляет факт (например, 'home_address' -> 'Ленина 10')"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO profile (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        ''', (key, value))
        conn.commit()

def get_all_facts() -> dict:
    """Достает все факты о пользователе"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM profile')
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}