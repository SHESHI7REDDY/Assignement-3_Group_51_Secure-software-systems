
"""Tests for role-based access control and audit logging."""

import pytest
from fastapi.testclient import TestClient

from app.auth import repository
from app.auth.audit import get_recent_audit_events
from app.auth.standalone import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Use an isolated database for each API test."""

    monkeypatch.setattr(
        repository,
        "DB_PATH",
        tmp_path / "rbac_test.db",
    )

    repository.initialise_database()

    with TestClient(app) as test_client:
        yield test_client


def create_account(client, username):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "password": "SecureExample123",
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def login(client, username):
    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SecureExample123",
        },
    )

    assert response.status_code == 200

    return {
        "Authorization":
            f"Bearer {response.json()['access_token']}"
    }


def test_voter_cannot_access_admin_audit(client):
    create_account(client, "normal_voter")
    headers = login(client, "normal_voter")

    response = client.get(
        "/auth/admin/audit",
        headers=headers,
    )

    assert response.status_code == 403


def test_admin_can_access_audit(client):
    user_id = create_account(client, "test_admin")

    # Assign admin role inside the isolated test database only.
    with repository.get_connection() as connection:
        connection.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            ("admin", user_id),
        )

    headers = login(client, "test_admin")

    response = client.get(
        "/auth/admin/audit",
        headers=headers,
    )

    assert response.status_code == 200
    assert "events" in response.json()


def test_admin_requires_authentication(client):
    response = client.get("/auth/admin/audit")

    assert response.status_code == 401


def test_registration_creates_audit_event(client):
    create_account(client, "new_voter")

    events = get_recent_audit_events()
    event_types = [e["event_type"] for e in events]

    assert "USER_REGISTERED" in event_types


def test_failed_login_creates_audit_event(client):
    create_account(client, "login_user")

    response = client.post(
        "/auth/login",
        json={
            "username": "login_user",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401

    events = get_recent_audit_events()
    event_types = [e["event_type"] for e in events]

    assert "LOGIN_FAILED" in event_types


def test_logout_creates_audit_event(client):
    create_account(client, "logout_user")
    headers = login(client, "logout_user")

    response = client.post(
        "/auth/logout",
        headers=headers,
    )

    assert response.status_code == 200

    events = get_recent_audit_events()
    event_types = [e["event_type"] for e in events]

    assert "LOGOUT_SUCCESS" in event_types


def test_audit_logs_exclude_secrets(client):
    create_account(client, "privacy_voter")
    headers = login(client, "privacy_voter")

    client.get("/auth/verify", headers=headers)

    events = get_recent_audit_events()

    for event in events:
        assert "password" not in event
        assert "access_token" not in event
        assert "mfa_secret" not in event


def test_voter_denial_is_audited(client):
    user_id = create_account(client, "denied_voter")
    headers = login(client, "denied_voter")

    response = client.get(
        "/auth/admin/audit",
        headers=headers,
    )

    assert response.status_code == 403

    events = get_recent_audit_events()

    assert any(
        event["event_type"] == "ADMIN_ACCESS_DENIED"
        and event["user_id"] == user_id
        for event in events
    )
