
"""Tests for the authentication frontend integration."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.auth.standalone import app
from app.shared.config import FRONTEND


FRONTEND_FILE = Path(FRONTEND) / "auth.html"


def test_auth_frontend_exists():
    """The standalone authentication page must exist."""
    assert FRONTEND_FILE.is_file()


def test_frontend_served_by_fastapi():
    """FastAPI must serve the frontend successfully."""
    with TestClient(app) as client:
        response = client.get("/static/auth.html")

    assert response.status_code == 200
    assert "Electronic Voting Platform" in response.text


def test_frontend_contains_authentication_forms():
    """The interface must provide registration and login."""
    content = FRONTEND_FILE.read_text(encoding="utf-8")

    assert 'id="register-form"' in content
    assert 'id="login-form"' in content
    assert 'id="mfa-code"' in content


def test_frontend_uses_authentication_endpoints():
    """Frontend must connect to the existing REST APIs."""
    content = FRONTEND_FILE.read_text(encoding="utf-8")

    assert "/auth/register" in content
    assert "/auth/login" in content
    assert "/auth/verify" in content
    assert "/auth/logout" in content


def test_frontend_avoids_persistent_token_storage():
    """The prototype must not persist bearer tokens in browser storage."""
    content = FRONTEND_FILE.read_text(encoding="utf-8")

    assert "localStorage" not in content
    assert "sessionStorage" not in content
    assert "innerHTML" not in content
