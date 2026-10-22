import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.candidates.repository import (
    get_connection,
    init_db,
    list_candidates,
)
from app.candidates.router import get_db_path, router
from app.candidates.security import Identity, get_identity


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.delenv("CAND_AUTH_VERIFY_URL", raising=False)

    path = tmp_path / "api.db"
    init_db(path)

    connection = get_connection(path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO elections (election_id, title)
                VALUES (?, ?)
                """,
                ("API-TEST", "Fictional API test"),
            )
    finally:
        connection.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_path] = lambda: path

    with TestClient(app) as client:
        yield app, client, path


def payload(**changes):
    data = {
        "election_id": "API-TEST",
        "name": "Sashi",
        "party": "Independent",
        "ballot_order": 1,
    }
    data.update(changes)
    return data


def use_identity(app, role="officer", elections=None):
    """Simulate verified identity only inside the test application."""
    identity = Identity(
        user_id="test-user",
        role=role,
        managed_election_ids=(
            ["API-TEST"] if elections is None else elections
        ),
    )
    app.dependency_overrides[get_identity] = lambda: identity


def test_authorised_creation_returns_201(api):
    app, client, path = api
    use_identity(app)

    response = client.post("/candidates", json=payload())

    assert response.status_code == 201
    assert response.json()["name"] == "Sashi"

    stored = list_candidates("API-TEST", path)
    assert len(stored) == 1
    assert (
        stored[0]["candidate_id"]
        == response.json()["candidate_id"]
    )


def test_missing_credentials_do_not_insert(api):
    _, client, path = api

    response = client.post("/candidates", json=payload())

    assert response.status_code == 401
    assert list_candidates("API-TEST", path) == []


@pytest.mark.parametrize(
    "role,elections",
    [
        ("voter", ["API-TEST"]),
        ("officer", ["OTHER"]),
        ("officer", []),
    ],
)
def test_forbidden_requests_do_not_insert(api, role, elections):
    app, client, path = api
    use_identity(app, role, elections)

    response = client.post(
        "/candidates",
        json=payload(),
        headers={"X-Mock-Role": "officer"},
    )

    assert response.status_code == 403
    assert list_candidates("API-TEST", path) == []


def test_duplicate_returns_409_without_extra_record(api):
    app, client, path = api
    use_identity(app)

    first = client.post("/candidates", json=payload())
    second = client.post(
        "/candidates",
        json=payload(name="Ved"),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(list_candidates("API-TEST", path)) == 1


def test_invalid_input_returns_422_without_insert(api):
    app, client, path = api
    use_identity(app)

    response = client.post(
        "/candidates",
        json=payload(name=""),
    )

    assert response.status_code == 422
    assert list_candidates("API-TEST", path) == []


def test_open_election_returns_409_without_insert(api):
    app, client, path = api
    use_identity(app)

    connection = get_connection(path)
    try:
        with connection:
            connection.execute(
                """
                UPDATE elections SET status = ?
                WHERE election_id = ?
                """,
                ("OPEN", "API-TEST"),
            )
    finally:
        connection.close()

    response = client.post("/candidates", json=payload())

    assert response.status_code == 409
    assert list_candidates("API-TEST", path) == []


def test_unknown_election_returns_404(api):
    app, client, path = api
    use_identity(app, elections=["MISSING"])

    response = client.post(
        "/candidates",
        json=payload(election_id="MISSING"),
    )

    assert response.status_code == 404
    assert list_candidates("API-TEST", path) == []


def test_unconfigured_auth_does_not_insert(api):
    _, client, path = api

    response = client.post(
        "/candidates",
        json=payload(),
        headers={"Authorization": "Bearer unverified-token"},
    )

    assert response.status_code == 503
    assert list_candidates("API-TEST", path) == []