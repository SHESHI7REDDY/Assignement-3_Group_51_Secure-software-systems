
"""Security audit logging for the authentication subsystem."""

import time

from app.auth.repository import get_connection


def initialise_audit_database():
    """Create a table for authentication security events."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )


ALLOWED_EVENTS = {
    "USER_REGISTERED",
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "SESSION_VERIFIED",
    "LOGOUT_SUCCESS",
    "ADMIN_ACCESS_DENIED",
    "ADMIN_ACCESS_GRANTED",
}


def record_security_event(
    event_type: str,
    user_id: int | None = None,
):
    """Store a security event without credentials or tokens."""

    if event_type not in ALLOWED_EVENTS:
        raise ValueError("Unsupported security event")

    initialise_audit_database()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO auth_audit_logs
            (user_id, event_type, created_at)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                event_type,
                int(time.time()),
            ),
        )


def get_recent_audit_events(limit: int = 50):
    """Retrieve recent authentication security events."""

    initialise_audit_database()

    limit = max(1, min(int(limit), 100))

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, event_type, created_at
            FROM auth_audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]
