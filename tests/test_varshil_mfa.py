
"""Unit tests for authentication MFA utilities."""

import pyotp

from app.auth.mfa import (
    generate_mfa_secret,
    generate_mfa_uri,
    verify_mfa_code,
)


def test_generate_unique_secrets():
    first = generate_mfa_secret()
    second = generate_mfa_secret()

    assert first != second


def test_generate_mfa_uri():
    secret = generate_mfa_secret()
    uri = generate_mfa_uri("test_voter", secret)

    assert uri.startswith("otpauth://totp/")
    assert "test_voter" in uri


def test_valid_mfa_code():
    secret = generate_mfa_secret()
    code = pyotp.TOTP(secret).now()

    assert verify_mfa_code(secret, code) is True


def test_invalid_mfa_code():
    secret = generate_mfa_secret()

    assert verify_mfa_code(secret, "ABCDEF") is False
    assert verify_mfa_code(secret, "123") is False
    assert verify_mfa_code(secret, "1234567") is False


def test_wrong_secret():
    first_secret = generate_mfa_secret()
    second_secret = generate_mfa_secret()

    code = pyotp.TOTP(first_secret).now()

    assert verify_mfa_code(second_secret, code) is False
