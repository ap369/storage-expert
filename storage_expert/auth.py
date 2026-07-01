import hashlib
import sqlite3
from pathlib import Path

import bcrypt

DB_PATH = Path("users.db")


def _prepare(password: str) -> bytes:
    # SHA-256 digest so bcrypt never receives >72 bytes
    return hashlib.sha256(password.encode()).hexdigest().encode()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users "
            "(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)"
        )


def add_user(username: str, password: str):
    password_hash = bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )


def verify_user(username: str, password: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return False
    return bcrypt.checkpw(_prepare(password), row[0].encode())
