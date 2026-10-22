import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.candidates.repository import get_connection
from app.candidates.router import get_db_path, router
from app.candidates.seed import seed_demo


@pytest.fixture
def candidate_api(tmp_path):
    db_path = tmp_path / "candidates.db"
    seed_demo(db_path)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_path] = lambda: db_path

    with TestClient(app) as client:
        yield client, db_path


def test_lists_seed_candidates_in_order(candidate_api):
    client, _ = candidate_api

    response = client.get(
        "/candidates", params={"election_id": "DEMO-A3-ELECTIONS"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["election_id"] == "DEMO-A3-ELECTIONS"
    assert len(body["candidates"]) == 4
    assert [
        item["ballot_order"] for item in body["candidates"]
    ] == [1, 2, 3, 4]


def test_unknown_election_returns_404(candidate_api):
    client, _ = candidate_api

    response = client.get(
        "/candidates", params={"election_id": "UNKNOWN"}
    )

    assert response.status_code == 404


def test_missing_election_returns_422(candidate_api):
    client, _ = candidate_api

    assert client.get("/candidates").status_code == 422


def test_invalid_election_identifier_returns_422(candidate_api):
    client, _ = candidate_api

    response = client.get(
        "/candidates",
        params={"election_id": "' OR 1=1 --"},
    )

    assert response.status_code == 422


def test_inactive_candidate_is_excluded(candidate_api):
    client, db_path = candidate_api
    connection = get_connection(db_path)

    try:
        with connection:
            connection.execute(
                "UPDATE candidates SET active = 0 WHERE candidate_id = ?",
                ("DEMO-C001",),
            )
    finally:
        connection.close()

    response = client.get(
        "/candidates", params={"election_id": "DEMO-A3-ELECTIONS"}
    )

    ids = [
        item["candidate_id"]
        for item in response.json()["candidates"]
    ]
    assert "DEMO-C001" not in ids
    assert len(ids) == 3


def test_reseeding_does_not_duplicate_candidates(candidate_api):
    client, db_path = candidate_api
    seed_demo(db_path)

    response = client.get(
        "/candidates", params={"election_id": "DEMO-A3-ELECTIONS"}
    )

    assert len(response.json()["candidates"]) == 4


def test_other_elections_candidates_are_excluded(candidate_api):
    client, db_path = candidate_api
    connection = get_connection(db_path)

    try:
        with connection:
            connection.execute(
                "INSERT INTO elections (election_id, title) VALUES (?, ?)",
                ("OTHER-2026", "Another fictional election"),
            )
            connection.execute(
                """
                INSERT INTO candidates (
                    candidate_id, election_id, name, party, ballot_order
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("OTHER-C001", "OTHER-2026", "Other Candidate", "Independent", 1),
            )
    finally:
        connection.close()

    response = client.get(
        "/candidates", params={"election_id": "DEMO-A3-ELECTIONS"}
    )

    ids = [
        item["candidate_id"]
        for item in response.json()["candidates"]
    ]
    assert "OTHER-C001" not in ids
    assert len(ids) == 4