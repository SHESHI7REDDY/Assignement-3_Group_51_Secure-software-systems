"""Shared identity contract and server-controlled demo voter links."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import repository
from app.auth.profiles import initialise_profiles, link_demo_voter
from app.auth.router import router
from app.auth.sessions import hash_token


@pytest.fixture
def identity_client(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "identity.db")
    initialise_profiles()
    application = FastAPI()
    application.include_router(router)
    with TestClient(application) as client:
        yield client


def login(client, name="demo_voter"):
    payload = {"username": name, "password": "FictionalPassword123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_unlinked_account_gets_no_voter_or_officer_permissions(identity_client):
    headers = login(identity_client)
    response = identity_client.get("/auth/verify", headers=headers)
    assert response.status_code == 200
    identity = response.json()
    assert identity["user_id"] == str(identity["id"])
    assert identity["role"] == "voter"
    assert identity["voter_id"] is None
    assert identity["managed_election_ids"] == []
    assert "password_hash" not in identity


def test_operator_link_comes_from_database(identity_client):
    headers = login(identity_client)
    link_demo_voter("demo_voter", "V0001")
    response = identity_client.get("/auth/verify", headers={
        **headers, "X-Voter-ID": "V0007", "X-Mock-Role": "officer",
    })
    assert response.json()["voter_id"] == "V0001"
    assert response.json()["role"] == "voter"
    assert response.json()["managed_election_ids"] == []


def test_same_link_can_be_repeated_without_remapping(identity_client):
    login(identity_client)
    link_demo_voter("demo_voter", "V0001")
    link_demo_voter("demo_voter", "V0001")
    with pytest.raises(ValueError, match="another voter"):
        link_demo_voter("demo_voter", "V0007")


def test_two_accounts_cannot_share_voter_id(identity_client):
    login(identity_client)
    login(identity_client, "second_voter")
    link_demo_voter("demo_voter", "V0001")
    with pytest.raises(ValueError, match="another account"):
        link_demo_voter("second_voter", "V0001")


def test_missing_and_revoked_tokens_rejected(identity_client):
    assert identity_client.get("/auth/verify").status_code == 401
    headers = login(identity_client)
    link_demo_voter("demo_voter", "V0001")
    assert identity_client.post("/auth/logout", headers=headers).status_code == 200
    assert identity_client.get("/auth/verify", headers=headers).status_code == 401


def test_expired_token_rejected(identity_client):
    headers = login(identity_client)
    raw = headers["Authorization"][7:]
    with repository.get_connection() as connection:
        connection.execute("UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
                           (int(time.time()) - 10, hash_token(raw)))
    assert identity_client.get("/auth/verify", headers=headers).status_code == 401


@pytest.mark.parametrize("voter_id", ["V0001' OR 1=1--", "V1", "../V0001"])
def test_invalid_link_rejected(identity_client, voter_id):
    login(identity_client)
    with pytest.raises(ValueError):
        link_demo_voter("demo_voter", voter_id)


def test_unknown_account_cannot_be_linked(identity_client):
    with pytest.raises(ValueError, match="Account not found"):
        link_demo_voter("unknown", "V0001")


def test_demo_roll_preparation_preserves_existing_voter_state(tmp_path, monkeypatch):
    from scripts.prepare_demo_roll import main
    from app.eligibility.repository import connect

    path = str(tmp_path / "roll.db")
    monkeypatch.setenv("ELIG_DB_PATH", path)
    monkeypatch.setenv("ELECTION_ID", "DEMO-A3-ELECTIONS")
    main()
    connection = connect(path)
    try:
        connection.execute("UPDATE electors SET disqualified = 1 WHERE voter_id = 'V0001'")
        connection.execute("INSERT INTO voting_status VALUES (?,?,1,?)",
                           ("DEMO-A3-ELECTIONS", "V0001", "ONLINE"))
        main()
        assert connection.execute("SELECT disqualified FROM electors WHERE voter_id = 'V0001'").fetchone()[0] == 1
        assert connection.execute("SELECT has_voted FROM voting_status WHERE voter_id = 'V0001'").fetchone()[0] == 1
    finally:
        connection.close()
