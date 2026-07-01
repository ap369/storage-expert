import sqlite3
from pathlib import Path

DB_PATH = Path("users.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users "
            "(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)"
        )


def add_user(username: str, password: str):
    from passlib.hash import bcrypt
    password_hash = bcrypt.hash(password)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )


def verify_user(username: str, password: str) -> bool:
    from passlib.hash import bcrypt
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return False
    return bcrypt.verify(password, row[0])
