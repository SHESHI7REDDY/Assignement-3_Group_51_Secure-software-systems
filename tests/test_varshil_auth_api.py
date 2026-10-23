
"""API tests for session verification and logout."""

import time

import pytest
from fastapi.testclient import TestClient

from app.auth import repository
from app.auth.sessions import hash_token
from app.auth.standalone import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Use a separate test database for each test."""

    monkeypatch.setattr(
        repository,
        "DB_PATH",
        tmp_path / "auth_api_test.db",
    )

    repository.initialise_database()

    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client):
    """Register a test user and obtain a session token."""

    registration = client.post(
        "/auth/register",
        json={
            "username": "test_voter",
            "password": "SecureExample123",
        },
    )

    assert registration.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "username": "test_voter",
            "password": "SecureExample123",
            "mfa_code": None,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def test_verify_without_token(client):
    """Unauthenticated requests must be rejected."""

    response = client.get("/auth/verify")

    assert response.status_code == 401


def test_verify_invalid_token(client):
    """An invalid bearer token must be rejected."""

    response = client.get(
        "/auth/verify",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401


def test_verify_valid_token(client):
    """A valid token must identify its account."""

    token = register_and_login(client)

    response = client.get(
        "/auth/verify",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "test_voter"
    assert data["role"] == "voter"
    assert "password" not in data
    assert "password_hash" not in data


def test_logout_without_token(client):
    """Logout requires authentication."""

    response = client.post("/auth/logout")

    assert response.status_code == 401


def test_logout_revokes_session(client):
    """A token cannot be used after logout."""

    token = register_and_login(client)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    before = client.get(
        "/auth/verify",
        headers=headers,
    )
    assert before.status_code == 200

    logout = client.post(
        "/auth/logout",
        headers=headers,
    )
    assert logout.status_code == 200

    after = client.get(
        "/auth/verify",
        headers=headers,
    )
    assert after.status_code == 401


def test_repeated_logout_rejected(client):
    """A revoked session cannot be logged out twice."""

    token = register_and_login(client)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    assert client.post(
        "/auth/logout",
        headers=headers,
    ).status_code == 200

    assert client.post(
        "/auth/logout",
        headers=headers,
    ).status_code == 401


def test_expired_token_rejected(client):
    """Expired tokens cannot access protected endpoints."""

    token = register_and_login(client)

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

    response = client.get(
        "/auth/verify",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401
