
"""Authentication security and business logic."""

import sqlite3
import time

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)
from fastapi import HTTPException, status

from app.auth.schemas import RegisterRequest, LoginRequest
from app.auth.repository import (
    initialise_database,
    create_user,
    get_user_by_username,
    get_user_mfa,
    save_pending_mfa,
    activate_mfa,
    consume_mfa_counter,
    is_account_locked,
    record_failed_login,
    reset_failed_logins,
)
from app.auth.mfa import (
    generate_mfa_secret,
    generate_mfa_uri,
    verify_mfa_code,
)
from app.auth.mfa_security import (
    encrypt_mfa_secret,
    decrypt_mfa_secret,
)
from app.auth.sessions import issue_session


password_hasher = PasswordHasher()

DUMMY_PASSWORD_HASH = password_hasher.hash(
    "DummyPasswordNotUsedForLogin123"
)


def hash_password(password: str) -> str:
    """Generate an Argon2id password hash."""
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Compare a password with its hash."""
    try:
        return password_hasher.verify(stored_hash, password)
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def invalid_credentials():
    """Raise a generic authentication failure."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
    )


def register_user(data: RegisterRequest) -> dict:
    """Register a new user with a hashed password."""

    initialise_database()

    existing = get_user_by_username(data.username)

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    password_hash = hash_password(data.password)

    try:
        user_id = create_user(data.username, password_hash)
    except sqlite3.IntegrityError:
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
    """Authenticate credentials and enforce account lockout."""

    initialise_database()

    user = get_user_by_username(data.username)

    if user is None:
        verify_password(data.password, DUMMY_PASSWORD_HASH)
        invalid_credentials()

    if is_account_locked(user["id"]):
        invalid_credentials()

    if not verify_password(
        data.password,
        user["password_hash"],
    ):
        record_failed_login(user["id"])
        invalid_credentials()

    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
    }


def begin_mfa_enrolment(
    username: str,
    password: str,
) -> dict:
    """Begin MFA setup after checking account credentials."""

    user = authenticate_user(
        LoginRequest(username=username, password=password)
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
            username,
            secret,
        ),
    }


def confirm_mfa_enrolment(
    username: str,
    password: str,
    code: str,
) -> dict:
    """Confirm MFA enrolment using the authenticator code."""

    user = authenticate_user(
        LoginRequest(username=username, password=password)
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
    """Issue a session only after completing authentication."""

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

        if not verify_mfa_code(secret, mfa_code):
            record_failed_login(user["id"])
            raise HTTPException(
                status_code=401,
                detail="Invalid MFA code",
            )

        counter = (
            int(time.time())
            // pyotp.TOTP(secret).interval
        )

        if not consume_mfa_counter(user["id"], counter):
            raise HTTPException(
                status_code=401,
                detail="MFA code already used",
            )

    # Check lockout again before issuing a session.
    if is_account_locked(user["id"]):
        invalid_credentials()

    token = issue_session(user["id"])

    reset_failed_logins(user["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
    }
