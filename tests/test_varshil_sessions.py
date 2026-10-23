
"""Security tests for authenticated sessions and MFA login."""

import time

import pyotp
import pytest
from fastapi import HTTPException

from app.auth import repository
from app.auth.mfa_security import encrypt_mfa_secret
from app.auth.service import (
    hash_password,
    login_with_session,
)
from app.auth.sessions import (
    hash_token,
    issue_session,
    validate_session,
    invalidate_session,
)


@pytest.fixture
def test_account(tmp_path, monkeypatch):
    """Use an isolated SQLite database for each test."""

    monkeypatch.setattr(
        repository,
        "DB_PATH",
        tmp_path / "sessions_test.db",
    )

    repository.initialise_database()

    user_id = repository.create_user(
        "session_test_user",
        hash_password("SecureExample123"),
    )

    return user_id


def test_valid_session(test_account):
    """A new session should identify its user."""

    token = issue_session(test_account)

    assert isinstance(token, str)
    assert validate_session(token) == test_account

    # Raw session tokens must not appear in storage.
    with repository.get_connection() as connection:
        row = connection.execute(
            "SELECT token_hash FROM auth_sessions"
        ).fetchone()

    assert row["token_hash"] == hash_token(token)
    assert row["token_hash"] != token


def test_invalid_session(test_account):
    """An unknown session token must be rejected."""

    assert validate_session("invalid-token") is None
    assert validate_session("") is None


def test_expired_session(test_account):
    """Expired sessions must not authenticate users."""

    token = issue_session(test_account)

    with repository.get_connection() as connection:
        connection.execute(
            """
            UPDATE auth_sessions
            SET expires_at = ?
            WHERE token_hash = ?
            """,
            (
                int(time.time()) - 10,
                hash_token(token),
            ),
        )

    assert validate_session(token) is None


def test_revoked_session(test_account):
    """Revocation must immediately invalidate a session."""

    token = issue_session(test_account)

    assert validate_session(token) == test_account
    assert invalidate_session(token) is True
    assert validate_session(token) is None


def test_password_login_creates_session(test_account):
    """Correct credentials should create an active session."""

    result = login_with_session(
        username="session_test_user",
        password="SecureExample123",
    )

    assert result["token_type"] == "bearer"
    assert result["expires_in"] == 1800

    token = result["access_token"]

    assert validate_session(token) == test_account


def test_incorrect_password_creates_no_session(test_account):
    """Incorrect credentials must not issue sessions."""

    with pytest.raises(HTTPException) as error:
        login_with_session(
            username="session_test_user",
            password="WrongPassword123",
        )

    assert error.value.status_code == 401

    with repository.get_connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM auth_sessions"
        ).fetchone()[0]

    assert count == 0


def test_mfa_required(test_account, monkeypatch):
    """MFA-enabled accounts cannot log in without a code."""

    from cryptography.fernet import Fernet

    monkeypatch.setenv(
        "AUTH_MFA_KEY",
        Fernet.generate_key().decode(),
    )

    secret = pyotp.random_base32()

    repository.save_pending_mfa(
        test_account,
        encrypt_mfa_secret(secret),
    )
    assert repository.activate_mfa(test_account)

    with pytest.raises(HTTPException) as error:
        login_with_session(
            username="session_test_user",
            password="SecureExample123",
        )

    assert error.value.status_code == 401

    with repository.get_connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM auth_sessions"
        ).fetchone()[0]

    assert count == 0


def test_mfa_code_replay_rejected(test_account, monkeypatch):
    """An accepted TOTP code must not create another session."""

    from cryptography.fernet import Fernet

    monkeypatch.setenv(
        "AUTH_MFA_KEY",
        Fernet.generate_key().decode(),
    )

    secret = pyotp.random_base32()

    repository.save_pending_mfa(
        test_account,
        encrypt_mfa_secret(secret),
    )
    assert repository.activate_mfa(test_account)

    code = pyotp.TOTP(secret).now()

    first = login_with_session(
        username="session_test_user",
        password="SecureExample123",
        mfa_code=code,
    )

    assert validate_session(first["access_token"]) == test_account

    with pytest.raises(HTTPException) as error:
        login_with_session(
            username="session_test_user",
            password="SecureExample123",
            mfa_code=code,
        )

    assert error.value.status_code == 401

    with repository.get_connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM auth_sessions"
        ).fetchone()[0]

    assert count == 1
