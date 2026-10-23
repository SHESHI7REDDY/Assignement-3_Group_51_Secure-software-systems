
"""SQLite persistence for the authentication subsystem."""

import sqlite3
import time
from pathlib import Path

from app.shared.config import DATA


DB_PATH = Path(DATA) / "auth_users.db"

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60


def get_connection():
    """Open a SQLite connection with dictionary-style rows."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialise_database():
    """Create and migrate authentication database tables."""

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

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(users)"
            )
        }

        new_columns = {
            "mfa_secret_encrypted": "TEXT",
            "mfa_pending_encrypted": "TEXT",
            "mfa_enabled": "INTEGER NOT NULL DEFAULT 0",
            "mfa_last_counter": "INTEGER NOT NULL DEFAULT -1",
            "failed_attempts": "INTEGER NOT NULL DEFAULT 0",
            "locked_until": "INTEGER NOT NULL DEFAULT 0",
        }

        for column, definition in new_columns.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
            ON auth_sessions(user_id)
            """
        )


def create_user(username: str, password_hash: str):
    """Store a user without storing a plaintext password."""

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
    """Retrieve authentication details using parameterised SQL."""

    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT id, username, password_hash, role
            FROM users WHERE username = ?
            """,
            (username,),
        ).fetchone()

        return dict(result) if result else None


def get_user_by_id(user_id: int):
    """Retrieve public user information."""

    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT id, username, role
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        return dict(result) if result else None


def get_user_mfa(user_id: int):
    """Retrieve a user's MFA settings."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, mfa_secret_encrypted,
                   mfa_pending_encrypted,
                   mfa_enabled, mfa_last_counter
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        return dict(row) if row else None


def save_pending_mfa(user_id: int, encrypted_secret: str) -> bool:
    """Save an encrypted pending MFA secret."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET mfa_pending_encrypted = ?
            WHERE id = ? AND mfa_enabled = 0
            """,
            (encrypted_secret, user_id),
        )
        return cursor.rowcount == 1


def activate_mfa(user_id: int) -> bool:
    """Activate a previously verified MFA secret."""

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
    """Return whether MFA is enabled."""

    with get_connection() as connection:
        row = connection.execute(
            "SELECT mfa_enabled FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        return bool(row["mfa_enabled"]) if row else False


def consume_mfa_counter(user_id: int, counter: int) -> bool:
    """Prevent reusing previously accepted TOTP intervals."""

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
    """Store a hashed session token."""

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO auth_sessions
            (token_hash, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token_hash, user_id, created_at, expires_at),
        )


def get_session(token_hash: str, current_time: int):
    """Return an active, unexpired session."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id FROM auth_sessions
            WHERE token_hash = ?
              AND revoked = 0
              AND expires_at > ?
            """,
            (token_hash, current_time),
        ).fetchone()

        return dict(row) if row else None


def revoke_session(token_hash: str) -> bool:
    """Revoke the specified session."""

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


def get_login_security(user_id: int):
    """Retrieve failed-attempt and lockout information."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT failed_attempts, locked_until
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        return dict(row) if row else None


def is_account_locked(user_id: int) -> bool:
    """Check whether the temporary lockout is active."""

    state = get_login_security(user_id)

    return bool(
        state and state["locked_until"] > int(time.time())
    )


def record_failed_login(user_id: int) -> bool:
    """Atomically update failures and apply temporary lockout."""

    now = int(time.time())

    with get_connection() as connection:
        # Reserve a write lock so attempts are counted consistently.
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT failed_attempts, locked_until
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return False

        if row["locked_until"] > now:
            return True

        attempts = (
            0 if row["locked_until"] != 0
            else row["failed_attempts"]
        ) + 1

        locked = attempts >= MAX_FAILED_ATTEMPTS
        locked_until = now + LOCKOUT_SECONDS if locked else 0

        connection.execute(
            """
            UPDATE users
            SET failed_attempts = ?, locked_until = ?
            WHERE id = ?
            """,
            (attempts, locked_until, user_id),
        )

        return locked


def reset_failed_logins(user_id: int) -> None:
    """Reset the failed-attempt count after successful login."""

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET failed_attempts = 0, locked_until = 0
            WHERE id = ?
            """,
            (user_id,),
        )
