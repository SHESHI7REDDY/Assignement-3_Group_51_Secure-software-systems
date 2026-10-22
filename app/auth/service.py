
"""Authentication security and business logic."""
from app.auth.mfa import (
    generate_mfa_secret,
    generate_mfa_uri,
    verify_mfa_code,
)
from app.auth.mfa_security import (
    encrypt_mfa_secret,
    decrypt_mfa_secret,
)
from app.auth.repository import (
    get_user_mfa,
    save_pending_mfa,
    activate_mfa,
)

from app.auth.schemas import RegisterRequest, LoginRequest
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

import time
import pyotp
from app.auth.repository import consume_mfa_counter
from app.auth.sessions import issue_session

# PasswordHasher uses Argon2id by default.
password_hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = password_hasher.hash(
    "DummyPasswordNotUsedForLogin123"
)


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


def authenticate_user(data: LoginRequest) -> dict:
    """Verify login credentials without revealing account existence."""

    initialise_database()

    user = get_user_by_username(data.username)

    if user is None:
        # Perform hash verification to reduce username enumeration
        # through differences in response time.
        verify_password(data.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
    }


def begin_mfa_enrolment(
    username: str,
    password: str,
) -> dict:
    """Start MFA setup after checking account credentials."""

    initialise_database()

    user = get_user_by_username(username)

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    if not verify_password(
        password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    mfa = get_user_mfa(user["id"])

    if mfa is None or mfa["mfa_enabled"]:
        raise HTTPException(
            status_code=409,
            detail="MFA setup is not available",
        )

    secret = generate_mfa_secret()
    encrypted = encrypt_mfa_secret(secret)

    if not save_pending_mfa(user["id"], encrypted):
        raise HTTPException(
            status_code=409,
            detail="MFA setup could not be started",
        )

    return {
        "message": "MFA setup started",
        "provisioning_uri": generate_mfa_uri(
            username, secret
        ),
    }


def confirm_mfa_enrolment(
    username: str,
    password: str,
    code: str,
) -> dict:
    """Verify the setup code before enabling MFA."""

    initialise_database()

    user = get_user_by_username(username)

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    if not verify_password(
        password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    mfa = get_user_mfa(user["id"])

    if (
        mfa is None
        or mfa["mfa_enabled"]
        or not mfa["mfa_pending_encrypted"]
    ):
        raise HTTPException(
            status_code=409,
            detail="No pending MFA setup",
        )

    secret = decrypt_mfa_secret(
        mfa["mfa_pending_encrypted"]
    )

    if not verify_mfa_code(secret, code):
        raise HTTPException(
            status_code=400,
            detail="Invalid MFA code",
        )

    if not activate_mfa(user["id"]):
        raise HTTPException(
            status_code=409,
            detail="MFA activation failed",
        )

    return {"message": "MFA enabled successfully"}


def login_with_session(
    username: str,
    password: str,
    mfa_code: str | None = None,
) -> dict:
    """Complete login and issue a session after MFA."""

    user = authenticate_user(
        LoginRequest(username=username, password=password)
    )

    mfa = get_user_mfa(user["id"])

    if mfa and mfa["mfa_enabled"]:
        if not mfa_code:
            raise HTTPException(
                status_code=401,
                detail="MFA code required",
            )

        secret = decrypt_mfa_secret(
            mfa["mfa_secret_encrypted"]
        )

        totp = pyotp.TOTP(secret)

        if not verify_mfa_code(secret, mfa_code):
            raise HTTPException(
                status_code=401,
                detail="Invalid MFA code",
            )

        counter = int(time.time()) // totp.interval

        if not consume_mfa_counter(user["id"], counter):
            raise HTTPException(
                status_code=401,
                detail="MFA code already used",
            )

    token = issue_session(user["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
    }
