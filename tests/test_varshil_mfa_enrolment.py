
"""Tests for encrypted MFA account enrolment."""

import pytest
import pyotp

from fastapi import HTTPException
from cryptography.fernet import Fernet

from app.auth import repository
from app.auth.service import (
    hash_password,
    begin_mfa_enrolment,
    confirm_mfa_enrolment,
)
from app.auth.mfa_security import (
    encrypt_mfa_secret,
    decrypt_mfa_secret,
)


@pytest.fixture
def test_user(tmp_path, monkeypatch):
    """Create an isolated database and encryption key."""
    monkeypatch.setattr(
        repository,
        "DB_PATH",
        tmp_path / "auth_test.db",
    )

    monkeypatch.setenv(
        "AUTH_MFA_KEY",
        Fernet.generate_key().decode(),
    )

    repository.initialise_database()

    user_id = repository.create_user(
        "mfa_test_user",
        hash_password("SecureExample123"),
    )

    return user_id


def test_mfa_encryption(test_user):
    secret = pyotp.random_base32()

    encrypted = encrypt_mfa_secret(secret)

    assert encrypted != secret
    assert decrypt_mfa_secret(encrypted) == secret


def test_mfa_setup(test_user):
    result = begin_mfa_enrolment(
        "mfa_test_user",
        "SecureExample123",
    )

    assert result["message"] == "MFA setup started"

    stored = repository.get_user_mfa(test_user)

    assert stored["mfa_pending_encrypted"] is not None
    assert stored["mfa_enabled"] == 0


def test_wrong_password_rejected(test_user):
    with pytest.raises(HTTPException) as error:
        begin_mfa_enrolment(
            "mfa_test_user",
            "WrongPassword123",
        )

    assert error.value.status_code == 401


def test_invalid_mfa_code_rejected(test_user):
    begin_mfa_enrolment(
        "mfa_test_user",
        "SecureExample123",
    )

    with pytest.raises(HTTPException) as error:
        confirm_mfa_enrolment(
            "mfa_test_user",
            "SecureExample123",
            "abcdef",
        )

    assert error.value.status_code == 400
    assert repository.get_mfa_status(test_user) is False


def test_successful_mfa_activation(test_user):
    result = begin_mfa_enrolment(
        "mfa_test_user",
        "SecureExample123",
    )

    uri = result["provisioning_uri"]
    secret = pyotp.parse_uri(uri).secret
    code = pyotp.TOTP(secret).now()

    response = confirm_mfa_enrolment(
        "mfa_test_user",
        "SecureExample123",
        code,
    )

    assert response["message"] == "MFA enabled successfully"
    assert repository.get_mfa_status(test_user) is True

    stored = repository.get_user_mfa(test_user)
    assert stored["mfa_pending_encrypted"] is None
    assert stored["mfa_secret_encrypted"] != secret


def test_repeated_activation_rejected(test_user):
    result = begin_mfa_enrolment(
        "mfa_test_user",
        "SecureExample123",
    )

    secret = pyotp.parse_uri(
        result["provisioning_uri"]
    ).secret

    code = pyotp.TOTP(secret).now()

    confirm_mfa_enrolment(
        "mfa_test_user",
        "SecureExample123",
        code,
    )

    with pytest.raises(HTTPException) as error:
        confirm_mfa_enrolment(
            "mfa_test_user",
            "SecureExample123",
            code,
        )

    assert error.value.status_code == 409
