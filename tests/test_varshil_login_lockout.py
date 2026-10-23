
"""Tests for failed-login protection and account lockout."""

import time

import pytest
from fastapi import HTTPException

from app.auth import repository
from app.auth.service import (
    hash_password,
    login_with_session,
)


@pytest.fixture
def test_account(tmp_path, monkeypatch):
    """Create an isolated test account."""
    monkeypatch.setattr(
        repository,
        "DB_PATH",
        tmp_path / "lockout_test.db",
    )

    repository.initialise_database()

    user_id = repository.create_user(
        "lockout_user",
        hash_password("SecureExample123"),
    )

    return user_id


def attempt_login(password):
    """Attempt authentication using the test account."""
    return login_with_session(
        username="lockout_user",
        password=password,
    )


def test_failed_attempt_recorded(test_account):
    with pytest.raises(HTTPException) as error:
        attempt_login("WrongPassword123")

    assert error.value.status_code == 401

    state = repository.get_login_security(test_account)
    assert state["failed_attempts"] == 1


def test_account_locked_after_five_failures(test_account):
    for _ in range(5):
        with pytest.raises(HTTPException):
            attempt_login("WrongPassword123")

    state = repository.get_login_security(test_account)

    assert state["failed_attempts"] == 5
    assert state["locked_until"] > int(time.time())
    assert repository.is_account_locked(test_account)


def test_correct_password_rejected_during_lockout(test_account):
    for _ in range(5):
        with pytest.raises(HTTPException):
            attempt_login("WrongPassword123")

    with pytest.raises(HTTPException) as error:
        attempt_login("SecureExample123")

    assert error.value.status_code == 401


def test_successful_login_resets_failures(test_account):
    for _ in range(3):
        with pytest.raises(HTTPException):
            attempt_login("WrongPassword123")

    response = attempt_login("SecureExample123")

    assert response["token_type"] == "bearer"

    state = repository.get_login_security(test_account)
    assert state["failed_attempts"] == 0
    assert state["locked_until"] == 0


def test_account_recovers_after_lockout(test_account):
    for _ in range(5):
        with pytest.raises(HTTPException):
            attempt_login("WrongPassword123")

    # Simulate the end of the lockout period.
    with repository.get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET locked_until = ?
            WHERE id = ?
            """,
            (int(time.time()) - 1, test_account),
        )

    response = attempt_login("SecureExample123")

    assert "access_token" in response

    state = repository.get_login_security(test_account)
    assert state["failed_attempts"] == 0
    assert state["locked_until"] == 0


def test_failed_attempts_do_not_reset_after_wrong_password(
    test_account,
):
    for _ in range(5):
        with pytest.raises(HTTPException):
            attempt_login("WrongPassword123")

    with repository.get_connection() as connection:
        connection.execute(
            """
            UPDATE users SET locked_until = ?
            WHERE id = ?
            """,
            (int(time.time()) - 1, test_account),
        )

    with pytest.raises(HTTPException):
        attempt_login("StillWrong123")

    state = repository.get_login_security(test_account)
    assert state["failed_attempts"] == 1
