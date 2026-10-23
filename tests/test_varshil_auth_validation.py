
"""Security validation tests for Varshil's authentication module."""

import pytest
from pydantic import ValidationError

from app.auth.schemas import RegisterRequest, LoginRequest
from app.auth.service import hash_password, verify_password


def test_valid_registration():
    user = RegisterRequest(
        username="varshil_test",
        password="SecureExample123",
    )
    assert user.username == "varshil_test"


@pytest.mark.parametrize(
    "username",
    ["ab", "invalid user", "user@email.com", "admin!"],
)
def test_invalid_registration_username(username):
    with pytest.raises(ValidationError):
        RegisterRequest(
            username=username,
            password="SecureExample123",
        )


@pytest.mark.parametrize(
    "password",
    ["short", "onlylettersabcd", "123456789012"],
)
def test_invalid_registration_password(password):
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="test_voter",
            password=password,
        )


def test_valid_login_input():
    login = LoginRequest(
        username="varshil_test",
        password="SecureExample123",
    )
    assert login.username == "varshil_test"


@pytest.mark.parametrize(
    "username,password",
    [
        ("ab", "SecureExample123"),
        ("invalid user", "SecureExample123"),
        ("valid_user", ""),
    ],
)
def test_invalid_login_input(username, password):
    with pytest.raises(ValidationError):
        LoginRequest(username=username, password=password)


def test_correct_password():
    password = "SecureExample123"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True
    assert password_hash != password


def test_incorrect_password():
    password_hash = hash_password("SecureExample123")

    assert verify_password("WrongPassword123", password_hash) is False


def test_invalid_password_hash():
    assert verify_password("SecureExample123", "invalid-hash") is False
