
"""Authentication security and business logic."""

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)
import sqlite3

from fastapi import HTTPException, status

from app.auth.repository import (
    initialise_database,
    create_user,
    get_user_by_username,
)
from app.auth.schemas import RegisterRequest
# PasswordHasher uses Argon2id by default.
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Generate a secure password hash."""
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password without exposing its hash."""
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def register_user(data: RegisterRequest) -> dict:
    """Register a user with a securely hashed password."""

    initialise_database()

    existing_user = get_user_by_username(data.username)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    password_hash = hash_password(data.password)

    try:
        user_id = create_user(data.username, password_hash)
    except sqlite3.IntegrityError:
        # Handles another request registering the same username.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        ) from None

    return {
        "id": user_id,
        "username": data.username,
        "role": "voter",
    }