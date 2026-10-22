from unittest.mock import patch

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.candidates.security import (
    Identity,
    ensure_election_permission,
    require_candidate_manager,
)


@pytest.fixture
def protected_api(monkeypatch):
    monkeypatch.setenv(
        "CAND_AUTH_VERIFY_URL",
        "http://127.0.0.1:8001/auth/verify",
    )

    app = FastAPI()

    # This endpoint exists only inside the tests.
    @app.get("/permission-check/{election_id}")
    def check(
        election_id: str,
        identity: Identity = Depends(require_candidate_manager),
    ):
        ensure_election_permission(identity, election_id)
        return {"allowed": True}

    with TestClient(app) as client:
        yield client


def identity_data(role="officer", elections=None):
    return {
        "user_id": "test-officer",
        "role": role,
        "managed_election_ids": (
            ["TEST-2026"] if elections is None else elections
        ),
    }


def test_missing_token_returns_401(protected_api):
    response = protected_api.get("/permission-check/TEST-2026")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role,elections,expected",
    [
        ("officer", ["TEST-2026"], 200),
        ("voter", ["TEST-2026"], 403),
        ("officer", ["OTHER"], 403),
        ("officer", [], 403),
    ],
)
def test_verified_identity_permissions(
    protected_api, role, elections, expected
):
    with patch(
        "app.candidates.security.httpx.Client"
    ) as client_class:
        remote = client_class.return_value.__enter__.return_value
        remote.get.return_value = httpx.Response(
            200,
            json=identity_data(role, elections),
        )

        response = protected_api.get(
            "/permission-check/TEST-2026",
            headers={
                "Authorization": "Bearer test-token",
                "X-Mock-Role": "officer",
            },
        )

        assert response.status_code == expected

        remote.get.assert_called_once_with(
            "http://127.0.0.1:8001/auth/verify",
            headers={"Authorization": "Bearer test-token"},
        )


@pytest.mark.parametrize(
    "remote_status,expected",
    [(401, 401), (503, 503), (302, 503)],
)
def test_failed_verification_denies_access(
    protected_api, remote_status, expected
):
    with patch(
        "app.candidates.security.httpx.Client"
    ) as client_class:
        remote = client_class.return_value.__enter__.return_value
        remote.get.return_value = httpx.Response(remote_status)

        response = protected_api.get(
            "/permission-check/TEST-2026",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == expected


def test_unconfigured_service_denies_access(
    protected_api, monkeypatch
):
    monkeypatch.delenv("CAND_AUTH_VERIFY_URL")

    response = protected_api.get(
        "/permission-check/TEST-2026",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 503


def test_malformed_identity_denies_access(protected_api):
    with patch(
        "app.candidates.security.httpx.Client"
    ) as client_class:
        remote = client_class.return_value.__enter__.return_value
        remote.get.return_value = httpx.Response(
            200, json={"role": "officer"}
        )

        response = protected_api.get(
            "/permission-check/TEST-2026",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 503


def test_service_timeout_denies_access(protected_api):
    with patch(
        "app.candidates.security.httpx.Client"
    ) as client_class:
        remote = client_class.return_value.__enter__.return_value
        remote.get.side_effect = httpx.ConnectTimeout("Test timeout")

        response = protected_api.get(
            "/permission-check/TEST-2026",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 503