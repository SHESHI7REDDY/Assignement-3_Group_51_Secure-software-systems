
"""SQLite persistence for the authentication subsystem."""

import sqlite3
from pathlib import Path

from app.shared.config import DATA


DB_PATH = Path(DATA) / "auth_users.db"


def get_connection():
    """Open a connection with dictionary-style rows."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialise_database():
    """Create the authentication table if it does not exist."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'voter',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_user(username: str, password_hash: str):
    """Store a user with a password hash, never a plaintext password."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
            """,
            (username, password_hash),
        )
        return cursor.lastrowid


def get_user_by_username(username: str):
    """Retrieve a user using a parameterised query."""
    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT id, username, password_hash, role
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        return dict(result) if result else None


def get_user_by_id(user_id: int):
    """Retrieve a user by their ID."""
    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT id, username, role
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        return dict(result) if result else None
