import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.candidates.repository import (
    create_candidate,
    get_connection,
    init_db,
)
from app.candidates.router import get_db_path, router
from app.candidates.schemas import CandidateCreate
from app.candidates.security import Identity, get_identity


@pytest.fixture
def api(tmp_path):
    path = tmp_path / "deactivation.db"
    init_db(path)

    connection = get_connection(path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO elections (election_id, title)
                VALUES (?, ?)
                """,
                ("DEACT-TEST", "Fictional deactivation test"),
            )
    finally:
        connection.close()

    candidate = create_candidate(
        CandidateCreate(
            election_id="DEACT-TEST",
            name="Sashi",
            party="Independent",
            ballot_order=1,
        ),
        path,
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db_path] = lambda: path
    app.dependency_overrides[get_identity] = lambda: Identity(
        user_id="test-officer",
        role="officer",
        managed_election_ids=["DEACT-TEST"],
    )

    with TestClient(app) as client:
        yield app, client, path, candidate["candidate_id"]


def deactivate(client, candidate_id, election_id="DEACT-TEST"):
    return client.post(
        f"/candidates/{candidate_id}/deactivate",
        params={"election_id": election_id},
    )


def stored_candidate(path):
    connection = get_connection(path)

    try:
        row = connection.execute(
            "SELECT * FROM candidates"
        ).fetchone()
        return dict(row)
    finally:
        connection.close()


def test_deactivation_preserves_record_and_hides_candidate(api):
    _, client, path, candidate_id = api

    response = deactivate(client, candidate_id)

    assert response.status_code == 200
    assert response.json()["active"] == 0

    stored = stored_candidate(path)
    assert stored["candidate_id"] == candidate_id
    assert stored["active"] == 0

    listing = client.get(
        "/candidates",
        params={"election_id": "DEACT-TEST"},
    )

    assert listing.status_code == 200
    assert listing.json()["candidates"] == []


def test_repeated_deactivation_is_idempotent(api):
    _, client, path, candidate_id = api

    assert deactivate(client, candidate_id).status_code == 200
    before = stored_candidate(path)

    assert deactivate(client, candidate_id).status_code == 200
    assert stored_candidate(path) == before


@pytest.mark.parametrize(
    "role,elections",
    [
        ("voter", ["DEACT-TEST"]),
        ("officer", ["OTHER"]),
    ],
)
def test_forbidden_deactivation_preserves_record(
    api, role, elections
):
    app, client, path, candidate_id = api

    app.dependency_overrides[get_identity] = lambda: Identity(
        user_id="test-user",
        role=role,
        managed_election_ids=elections,
    )

    before = stored_candidate(path)

    assert deactivate(client, candidate_id).status_code == 403
    assert stored_candidate(path) == before


@pytest.mark.parametrize("status", ["OPEN", "CLOSED"])
def test_locked_election_prevents_deactivation(api, status):
    _, client, path, candidate_id = api

    connection = get_connection(path)
    try:
        with connection:
            connection.execute(
                """
                UPDATE elections SET status = ?
                WHERE election_id = ?
                """,
                (status, "DEACT-TEST"),
            )
    finally:
        connection.close()

    before = stored_candidate(path)

    assert deactivate(client, candidate_id).status_code == 409
    assert stored_candidate(path) == before


def test_missing_credentials_prevents_deactivation(api):
    app, client, path, candidate_id = api
    del app.dependency_overrides[get_identity]

    before = stored_candidate(path)

    assert deactivate(client, candidate_id).status_code == 401
    assert stored_candidate(path) == before


def test_unknown_candidate_returns_404(api):
    _, client, path, _ = api
    before = stored_candidate(path)

    assert deactivate(client, "MISSING").status_code == 404
    assert stored_candidate(path) == before


def test_wrong_election_cannot_target_candidate(api):
    app, client, path, candidate_id = api

    app.dependency_overrides[get_identity] = lambda: Identity(
        user_id="other-officer",
        role="officer",
        managed_election_ids=["OTHER"],
    )

    before = stored_candidate(path)

    response = deactivate(
        client,
        candidate_id,
        election_id="OTHER",
    )

    assert response.status_code == 404
    assert stored_candidate(path) == before