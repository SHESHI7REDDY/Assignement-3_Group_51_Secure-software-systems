
"""Secure opaque session tokens."""

import hashlib
import secrets
import time

from app.auth.repository import (
    initialise_database,
    create_session,
    get_session,
    revoke_session,
)

SESSION_DURATION = 1800


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(user_id: int) -> str:
    """Issue a random 30-minute session token."""
    initialise_database()

    token = secrets.token_urlsafe(32)
    now = int(time.time())

    create_session(
        user_id=user_id,
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + SESSION_DURATION,
    )

    return token


def validate_session(token: str):
    """Return the user ID for an active session."""
    initialise_database()

    if not token:
        return None

    record = get_session(hash_token(token), int(time.time()))

    return record["user_id"] if record else None


def invalidate_session(token: str) -> bool:
    """Revoke a session token."""
    return revoke_session(hash_token(token))
