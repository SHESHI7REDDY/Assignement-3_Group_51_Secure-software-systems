"""Fixtures for Ved's eligibility security tests: fresh fictional DB per test."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.eligibility.config import Settings, get_settings
from app.eligibility.repository import seed
from app.eligibility.security import issue_mock_token
from app.eligibility.standalone import create_app


@pytest.fixture
def settings(tmp_path):
    s = Settings(db_path=str(tmp_path / "test.db"), election_id="FED-2026",
                 election_date=date(2026, 12, 5), auth_secret="test-secret-" + "x" * 40,
                 pseudonym_key="test-pseudo-" + "y" * 40, mock_auth=True)
    seed(s)
    return s


@pytest.fixture
def client(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture
def auth(settings):
    def make(role="voter", voter_id="V0001", user_id=None, ttl=None):
        token = issue_mock_token(settings, user_id or f"u-{role}-{voter_id}", role,
                                 voter_id if role == "voter" else None, ttl)
        return {"Authorization": f"Bearer {token}"}
    return make
