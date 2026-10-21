
"""Authentication security and business logic."""

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)

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
