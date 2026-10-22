import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.candidates.repository import (
    create_candidate,
    get_connection,
    init_db,
    list_candidates,
)
from app.candidates.router import get_db_path, router
from app.candidates.schemas import CandidateCreate
from app.candidates.security import Identity, get_identity


@pytest.fixture
def editing_api(tmp_path):
    path = tmp_path / "editing.db"
    init_db(path)

    connection = get_connection(path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO elections (election_id, title)
                VALUES (?, ?)
                """,
                ("EDIT-TEST", "Fictional editing test"),
            )
    finally:
        connection.close()

    first = create_candidate(
        CandidateCreate(
            election_id="EDIT-TEST",
            name="Sashi",
            party="Independent",
            ballot_order=1,
        ),
        path,
    )

    create_candidate(
        CandidateCreate(
            election_id="EDIT-TEST",
            name="Ved",
            party="Independent",
            ballot_order=2,
        ),
        path,
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_path] = lambda: path

    officer = Identity(
        user_id="officer-test",
        role="officer",
        managed_election_ids=["EDIT-TEST"],
    )
    app.dependency_overrides[get_identity] = lambda: officer

    with TestClient(app) as client:
        yield app, client, path, first["candidate_id"]


def edit(client, candidate_id, body, election_id="EDIT-TEST"):
    return client.patch(
        f"/candidates/{candidate_id}",
        params={"election_id": election_id},
        json=body,
    )


def test_partial_edit_preserves_omitted_fields(editing_api):
    _, client, path, candidate_id = editing_api

    response = edit(
        client, candidate_id, {"name": "Sashi Updated"}
    )

    assert response.status_code == 200
    assert response.json()["party"] == "Independent"
    assert response.json()["ballot_order"] == 1
    assert (
        list_candidates("EDIT-TEST", path)[0]["name"]
        == "Sashi Updated"
    )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": ""},
        {"name": None},
        {"ballot_order": 0},
        {"election_id": "OTHER"},
        {"active": 0},
    ],
)
def test_invalid_edits_leave_records_unchanged(editing_api, body):
    _, client, path, candidate_id = editing_api
    before = list_candidates("EDIT-TEST", path)

    assert edit(client, candidate_id, body).status_code == 422
    assert list_candidates("EDIT-TEST", path) == before


def test_duplicate_position_rolls_back_all_changes(editing_api):
    _, client, path, candidate_id = editing_api
    before = list_candidates("EDIT-TEST", path)

    response = edit(
        client,
        candidate_id,
        {"name": "Changed", "ballot_order": 2},
    )

    assert response.status_code == 409
    assert list_candidates("EDIT-TEST", path) == before


@pytest.mark.parametrize("status", ["OPEN", "CLOSED"])
def test_locked_election_rejects_edit(editing_api, status):
    _, client, path, candidate_id = editing_api

    connection = get_connection(path)
    try:
        with connection:
            connection.execute(
                """
                UPDATE elections SET status = ?
                WHERE election_id = ?
                """,
                (status, "EDIT-TEST"),
            )
    finally:
        connection.close()

    before = list_candidates("EDIT-TEST", path)

    response = edit(client, candidate_id, {"name": "Changed"})

    assert response.status_code == 409
    assert list_candidates("EDIT-TEST", path) == before


@pytest.mark.parametrize(
    "role,elections",
    [
        ("voter", ["EDIT-TEST"]),
        ("officer", ["OTHER"]),
    ],
)
def test_forbidden_edit_does_not_change_records(
    editing_api, role, elections
):
    app, client, path, candidate_id = editing_api

    app.dependency_overrides[get_identity] = lambda: Identity(
        user_id="other-user",
        role=role,
        managed_election_ids=elections,
    )

    before = list_candidates("EDIT-TEST", path)

    response = edit(client, candidate_id, {"name": "Changed"})

    assert response.status_code == 403
    assert list_candidates("EDIT-TEST", path) == before


def test_missing_credentials_rejects_edit(editing_api):
    app, client, path, candidate_id = editing_api
    del app.dependency_overrides[get_identity]

    before = list_candidates("EDIT-TEST", path)

    response = edit(client, candidate_id, {"name": "Changed"})

    assert response.status_code == 401
    assert list_candidates("EDIT-TEST", path) == before


def test_unknown_candidate_returns_404(editing_api):
    _, client, path, _ = editing_api
    before = list_candidates("EDIT-TEST", path)

    response = edit(client, "MISSING", {"name": "Changed"})

    assert response.status_code == 404
    assert list_candidates("EDIT-TEST", path) == before


def test_candidate_cannot_be_accessed_through_another_election(
    editing_api,
):
    app, client, path, candidate_id = editing_api

    app.dependency_overrides[get_identity] = lambda: Identity(
        user_id="other-officer",
        role="officer",
        managed_election_ids=["OTHER"],
    )

    before = list_candidates("EDIT-TEST", path)

    response = edit(
        client,
        candidate_id,
        {"name": "Changed"},
        election_id="OTHER",
    )

    assert response.status_code == 404
    assert list_candidates("EDIT-TEST", path) == before