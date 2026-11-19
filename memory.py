# memory.py
import sqlite3
import json
import time
from contextlib import contextmanager

DB_PATH = "uje_memory.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        # Профиль пользователя привязан к сессии
        db.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (session_id, key)
            )
        """)
        # Ожидаемые действия (pending) тоже по сессиям
        db.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                session_id TEXT PRIMARY KEY,
                action TEXT,
                params TEXT,
                expires REAL
            )
        """)
        # События для аналитики / выгрузки CSV (потребность Госкомитета)
        db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                event_type TEXT,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Лиды (заявки) — пригодится и НТК, и Госкому
        db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                partner_id TEXT,
                name TEXT,
                phone TEXT,
                tour_interest TEXT,
                consent_given INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Миграция: если старая таблица profile без session_id — пересоздать
        cols = [r["name"] for r in db.execute("PRAGMA table_info(profile)").fetchall()]
        if cols and "session_id" not in cols:
            db.execute("DROP TABLE profile")
            db.execute("""
                CREATE TABLE profile (
                    session_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (session_id, key)
                )
            """)
        cols_p = [r["name"] for r in db.execute("PRAGMA table_info(pending)").fetchall()]
        if cols_p and "session_id" not in cols_p:
            db.execute("DROP TABLE pending")
            db.execute("""
                CREATE TABLE pending (
                    session_id TEXT PRIMARY KEY,
                    action TEXT,
                    params TEXT,
                    expires REAL
                )
            """)

init_db()

# ===== ОСНОВНЫЕ ФУНКЦИИ ПАМЯТИ (все требуют session_id) =====

def save_fact(session_id: str, key: str, value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    else:
        value = str(value)
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO profile (session_id, key, value) VALUES (?, ?, ?)",
            (session_id, key, value)
        )

def get_fact(session_id: str, key: str, default=None):
    with get_db() as db:
        row = db.execute(
            "SELECT value FROM profile WHERE session_id=? AND key=?",
            (session_id, key)
        ).fetchone()
        return row["value"] if row else default

def get_all_facts(session_id: str) -> dict:
    with get_db() as db:
        rows = db.execute(
            "SELECT key, value FROM profile WHERE session_id=?",
            (session_id,)
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

def clear_all_facts(session_id: str):
    with get_db() as db:
        db.execute("DELETE FROM profile WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM pending WHERE session_id=?", (session_id,))

# ===== PENDING (ожидание действий) =====

def save_pending(session_id: str, action: str, params: str = "", ttl: int = 1800):
    expires = time.time() + ttl
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO pending (session_id, action, params, expires) VALUES (?, ?, ?, ?)",
            (session_id, action, params, expires)
        )

def get_pending(session_id: str):
    with get_db() as db:
        row = db.execute(
            "SELECT action, params, expires FROM pending WHERE session_id=?",
            (session_id,)
        ).fetchone()
        if row and row["expires"] > time.time():
            return {"action": row["action"], "params": row["params"]}
        elif row:
            db.execute("DELETE FROM pending WHERE session_id=?", (session_id,))
        return None

def clear_pending(session_id: str):
    with get_db() as db:
        db.execute("DELETE FROM pending WHERE session_id=?", (session_id,))

# ===== СОБЫТИЯ (для аналитики и CSV-выгрузки) =====

def log_event(session_id: str, event_type: str, payload: dict = None):
    data = json.dumps(payload or {}, ensure_ascii=False)
    with get_db() as db:
        db.execute(
            "INSERT INTO events (session_id, event_type, payload) VALUES (?, ?, ?)",
            (session_id, event_type, data)
        )

def export_events_csv(from_date: str = None, to_date: str = None) -> list:
    """Возвращает список событий для выгрузки. Используется эндпоинтом /api/export."""
    query = "SELECT session_id, event_type, payload, created_at FROM events"
    params = []
    conditions = []
    if from_date:
        conditions.append("created_at >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("created_at <= ?")
        params.append(to_date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

# ===== ЛИДЫ (заявки на туры/услуги) =====

def save_lead(session_id: str, partner_id: str, name: str, phone: str,
              tour_interest: str = "", consent_given: bool = False):
    with get_db() as db:
        db.execute(
            """INSERT INTO leads (session_id, partner_id, name, phone, tour_interest, consent_given)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, partner_id, name, phone, tour_interest, 1 if consent_given else 0)
        )

def get_leads(partner_id: str = None) -> list:
    with get_db() as db:
        if partner_id:
            rows = db.execute(
                "SELECT * FROM leads WHERE partner_id=? ORDER BY created_at DESC",
                (partner_id,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]