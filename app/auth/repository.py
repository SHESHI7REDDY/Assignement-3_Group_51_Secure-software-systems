
"""SQLite persistence for the authentication subsystem."""

import sqlite3
from pathlib import Path

from app.shared.config import DATA


DB_PATH = Path(DATA) / "auth_users.db"


def get_connection():
    """Open a connection with dictionary-style rows."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialise_database():
    """Create user, MFA and session database structures."""

    with get_connection() as connection:

        # Create the users table.
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

        # Check existing columns for MFA migration.
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(users)"
            )
        }

        # MFA columns.
        new_columns = {
            "mfa_secret_encrypted": "TEXT",
            "mfa_pending_encrypted": "TEXT",
            "mfa_enabled": "INTEGER NOT NULL DEFAULT 0",
            "mfa_last_counter": "INTEGER NOT NULL DEFAULT -1",
        }

        # Add missing MFA columns.
        for column, definition in new_columns.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )

        # Create session table.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id)
                    REFERENCES users(id)
            )
            """
        )

        # Index for user session lookups.
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_auth_sessions_user_id
            ON auth_sessions(user_id)
            """
        )


def create_user(username: str, password_hash: str):
    """Store a user with a password hash, never plaintext."""

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
    """Retrieve a user using a parameterised SQL query."""

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
    """Retrieve public account information."""

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


def get_user_mfa(user_id: int):
    """Retrieve MFA settings for an existing user."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id,
                   mfa_secret_encrypted,
                   mfa_pending_encrypted,
                   mfa_enabled,
                   mfa_last_counter
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        return dict(row) if row else None


def save_pending_mfa(
    user_id: int,
    encrypted_secret: str,
) -> bool:
    """Store encrypted MFA setup data before activation."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET mfa_pending_encrypted = ?
            WHERE id = ?
              AND mfa_enabled = 0
            """,
            (encrypted_secret, user_id),
        )

        return cursor.rowcount == 1


def activate_mfa(user_id: int) -> bool:
    """Activate MFA after the service verifies a TOTP code."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET mfa_secret_encrypted = mfa_pending_encrypted,
                mfa_pending_encrypted = NULL,
                mfa_enabled = 1,
                mfa_last_counter = -1
            WHERE id = ?
              AND mfa_enabled = 0
              AND mfa_pending_encrypted IS NOT NULL
            """,
            (user_id,),
        )

        return cursor.rowcount == 1


def get_mfa_status(user_id: int) -> bool:
    """Check whether MFA is enabled."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT mfa_enabled
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        return bool(row["mfa_enabled"]) if row else False


def consume_mfa_counter(
    user_id: int,
    counter: int,
) -> bool:
    """Prevent reuse of previously accepted MFA time steps."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET mfa_last_counter = ?
            WHERE id = ?
              AND mfa_enabled = 1
              AND mfa_last_counter < ?
            """,
            (counter, user_id, counter),
        )

        return cursor.rowcount == 1


def create_session(
    user_id: int,
    token_hash: str,
    created_at: int,
    expires_at: int,
):
    """Store a hashed authentication session token."""

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO auth_sessions (
                token_hash,
                user_id,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                token_hash,
                user_id,
                created_at,
                expires_at,
            ),
        )


def get_session(token_hash: str, current_time: int):
    """Retrieve an active, unexpired session."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id
            FROM auth_sessions
            WHERE token_hash = ?
              AND revoked = 0
              AND expires_at > ?
            """,
            (token_hash, current_time),
        ).fetchone()

        return dict(row) if row else None


def revoke_session(token_hash: str) -> bool:
    """Invalidate a stored session."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE auth_sessions
            SET revoked = 1
            WHERE token_hash = ?
              AND revoked = 0
            """,
            (token_hash,),
        )

        return cursor.rowcount == 1
