"""Real accepted ballots -> closed election -> admin count -> publication.

All accounts, ballot keys and databases are temporary and isolated.
"""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import repository as accounts
from app.auth.demo_admin import grant
from app.auth.profiles import initialise_profiles, link_demo_voter
from app.auth.router import router as auth_router
from app.ballot.integration import get_candidate_db_path
from app.ballot.lifecycle import transition
from app.ballot.router import router as ballot_router
from app.candidates.seed import seed_demo
from app.eligibility import repository as roll
from app.eligibility.config import Settings, get_settings
from app.results import audit, platform, repository
from app.results.platform_router import router

ELECTION = "DEMO-A3-ELECTIONS"
BODY = {"election_id": ELECTION, "preferences": [
    {"candidate_id": f"DEMO-C00{rank}", "rank": rank} for rank in range(1, 5)
]}


def register(client, username):
    credentials = {"username": username, "password": "FictionalPassword123"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    return credentials


def login(client, credentials):
    response = client.post("/auth/login", json=credentials)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "DB_PATH", tmp_path / "users.db")
    monkeypatch.setenv("RESULTS_DB_PATH", str(tmp_path / "results.db"))
    key = bytes(range(32))
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", key.hex())
    # A configured old mock token must still not grant integrated access.
    monkeypatch.setenv("RESULTS_ADMIN_TOKEN", "old-demo-token-does-not-grant-access")
    ballot_key = tmp_path / "ballot.key"
    monkeypatch.setenv("BALLOT_KEY_FILE", str(ballot_key))
    initialise_profiles()
    settings = Settings(db_path=str(tmp_path / "roll.db"), election_id=ELECTION,
                        election_date=date(2026, 12, 5), mock_auth=False,
                        auth_secret="test-auth-key", pseudonym_key="test-pseudonym-key")
    roll.seed(settings)
    candidate_path = tmp_path / "candidates.db"
    seed_demo(candidate_path)
    transition(ELECTION, "OPEN", candidate_path)
    app = FastAPI()
    for item in (auth_router, ballot_router, router):
        app.include_router(item)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_candidate_db_path] = lambda: candidate_path
    with TestClient(app) as client:
        voter = register(client, "demo_voter")
        link_demo_voter("demo_voter", "V0001")
        voter_headers = login(client, voter)
        receipt = client.post("/ballots/submit", json=BODY, headers=voter_headers)
        assert receipt.status_code == 200
        admin = register(client, "results_admin")
        grant("results_admin")
        admin_headers = login(client, admin)
        yield SimpleNamespace(client=client, settings=settings, candidates=candidate_path,
                              db=tmp_path / "results.db", key=key, ballot_key=ballot_key,
                              voter=voter_headers, admin=admin_headers)


def close(system):
    transition(ELECTION, "CLOSED", system.candidates)


def count(system):
    return system.client.post("/results/count", headers=system.admin)


def publish(system):
    return system.client.post(f"/results/{ELECTION}/publish", headers=system.admin)


def result(system):
    return repository.get_count(ELECTION, system.db)


def test_complete_real_vote_count_publish_read_and_audit(system):
    assert system.client.get(f"/results/{ELECTION}").status_code == 404
    close(system)
    response = count(system)
    assert response.status_code == 201
    assert response.json()["election_id"] == ELECTION
    assert response.json()["winner_id"] == "DEMO-C001"
    assert response.json()["total_ballots"] == 1  # Not the old ten-ballot fixture.
    assert response.json()["rounds"][0]["totals"] == {
        "DEMO-C001": 1, "DEMO-C002": 0, "DEMO-C003": 0, "DEMO-C004": 0}
    assert response.json()["candidates"][0]["name"] == "Varshil"
    assert system.client.get(f"/results/{ELECTION}").status_code == 404
    assert publish(system).status_code == 200
    public = system.client.get(f"/results/{ELECTION}")
    assert public.status_code == 200 and public.json()["status"] == "published"
    assert set(public.json()) == {"election_id", "status", "winner_id", "total_ballots",
                                  "rounds", "published_at", "candidates"}
    for private in ("encrypted_ballot", "voter_id", "username", "ballot_id", "source_digest", "result_mac"):
        assert private not in public.text
    verify = system.client.get(f"/results/{ELECTION}/audit/verify", headers=system.admin)
    assert verify.json()["integrity_valid"] is True
    events = system.client.get(f"/results/{ELECTION}/audit", headers=system.admin)
    assert [item["event_type"] for item in events.json()["events"]] == ["COUNT_COMPLETED", "RESULT_PUBLISHED"]
    assert "actor_id" not in events.text


def test_open_election_cannot_be_counted_or_published(system):
    assert count(system).status_code == 409
    assert publish(system).status_code == 409
    assert result(system) is None
    assert not audit.read_events(system.db)


@pytest.mark.parametrize("endpoint,method", [
    ("/results/count", "post"), (f"/results/{ELECTION}/publish", "post"),
    (f"/results/{ELECTION}/audit", "get"), (f"/results/{ELECTION}/audit/verify", "get"),
])
def test_results_actions_require_real_admin_session(system, endpoint, method):
    request = getattr(system.client, method)
    assert request(endpoint).status_code == 401
    assert request(endpoint, headers=system.voter).status_code == 403
    assert request(endpoint, headers={"X-Results-Admin-Token": "old-demo-token-does-not-grant-access"}).status_code == 401
    assert result(system) is None


def test_officer_is_not_a_results_admin(system):
    credentials = register(system.client, "separate_officer")
    with accounts.get_connection() as connection:
        connection.execute("UPDATE users SET role='officer' WHERE username='separate_officer'")
    headers = login(system.client, credentials)
    assert system.client.post("/results/count", headers=headers).status_code == 403


def test_revoked_admin_session_rejected(system):
    assert system.client.post("/auth/logout", headers=system.admin).status_code == 200
    assert count(system).status_code == 401


def test_duplicate_count_and_publication_do_not_change_saved_result(system):
    close(system)
    assert count(system).status_code == 201
    first = result(system)
    assert count(system).status_code == 409 and result(system) == first
    assert publish(system).status_code == 200
    published = result(system)
    assert publish(system).status_code == 409 and result(system) == published
    assert len(audit.read_events(system.db)) == 2


def test_wrong_election_is_not_published_or_read(system):
    close(system)
    assert count(system).status_code == 201
    assert system.client.post("/results/DEMO-001/publish", headers=system.admin).status_code == 404
    assert system.client.get("/results/DEMO-001").status_code == 404
    assert result(system)["status"] == "counted"


def test_zero_accepted_ballots_are_not_replaced_with_fixture_data(system):
    close(system)
    with closing(roll.connect(system.settings.db_path)) as connection:
        connection.execute("DELETE FROM accepted_ballots")
    assert count(system).status_code == 409
    assert result(system) is None


def test_missing_ballot_key_is_not_recreated_during_counting(system):
    close(system)
    system.ballot_key.unlink()
    assert count(system).status_code == 503
    assert not system.ballot_key.exists()
    assert result(system) is None


@pytest.mark.parametrize("invalid", ["changed_ciphertext", "malformed_payload", "wrong_ranks"])
def test_bad_ballot_blocks_count_without_partial_result(system, invalid):
    close(system)
    value = "changed-and-invalid"
    if invalid != "changed_ciphertext":
        payload = {"preferences": BODY["preferences"], "voter_id": "V0001"}
        if invalid == "wrong_ranks":
            payload = {"preferences": [{"candidate_id": "DEMO-C001", "rank": 1}]}
        value = Fernet(system.ballot_key.read_bytes()).encrypt(json.dumps(payload).encode()).decode()
    with closing(roll.connect(system.settings.db_path)) as connection:
        connection.execute("UPDATE accepted_ballots SET encrypted_ballot = ?", (value,))
    assert count(system).status_code == 409
    assert result(system) is None and not audit.read_events(system.db)


def test_count_and_audit_roll_back_together(system, monkeypatch):
    close(system)
    def broken(*args, **kwargs):
        raise RuntimeError("internal test failure")
    with monkeypatch.context() as patch:
        patch.setattr(audit, "append_event", broken)
        response = count(system)
        assert response.status_code == 503
        assert "internal test failure" not in response.text
    assert result(system) is None and not audit.read_events(system.db)
    with sqlite3.connect(system.db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM platform_count_sources").fetchone()[0] == 0
    assert count(system).status_code == 201


def test_publication_and_audit_roll_back_together(system, monkeypatch):
    close(system)
    assert count(system).status_code == 201
    first = result(system)
    def broken(*args, **kwargs):
        raise RuntimeError("internal failure")
    with monkeypatch.context() as patch:
        patch.setattr(audit, "append_event", broken)
        assert publish(system).status_code == 503
    assert result(system) == first
    assert len(audit.read_events(system.db)) == 1
    assert system.client.get(f"/results/{ELECTION}").status_code == 404
    assert publish(system).status_code == 200


def test_tampered_audit_blocks_publication(system):
    close(system)
    assert count(system).status_code == 201
    with sqlite3.connect(system.db) as connection:
        connection.execute("UPDATE results_audit_events SET outcome='failure'")
    assert system.client.get(f"/results/{ELECTION}/audit/verify", headers=system.admin).json()["integrity_valid"] is False
    assert publish(system).status_code == 409
    assert result(system)["status"] == "counted"


def test_tampered_count_cannot_be_published_or_disclosed(system):
    close(system)
    assert count(system).status_code == 201
    with sqlite3.connect(system.db) as connection:
        connection.execute("UPDATE election_results SET winner_id='DEMO-C004'")
    assert publish(system).status_code == 409
    assert system.client.get(f"/results/{ELECTION}").status_code == 409


def test_tampered_source_after_count_blocks_publication(system):
    close(system)
    assert count(system).status_code == 201
    with closing(roll.connect(system.settings.db_path)) as connection:
        connection.execute("DELETE FROM accepted_ballots")
    assert publish(system).status_code == 409
    assert result(system)["status"] == "counted"


def test_source_change_after_publication_blocks_public_result(system):
    close(system)
    assert count(system).status_code == 201 and publish(system).status_code == 200
    with closing(roll.connect(system.settings.db_path)) as connection:
        connection.execute("DELETE FROM accepted_ballots")
    assert system.client.get(f"/results/{ELECTION}").status_code == 409


def test_missing_hmac_key_fails_closed(system, monkeypatch):
    close(system)
    monkeypatch.delenv("RESULTS_AUDIT_HMAC_KEY")
    assert count(system).status_code == 503
    assert result(system) is None


def test_two_concurrent_counts_save_exactly_one_snapshot(system):
    close(system)
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: count(system).status_code, range(2)))
    assert sorted(statuses) == [201, 409]
    assert len(audit.read_events(system.db)) == 1


def test_unresolved_tie_is_not_published_as_a_winner(system):
    second = register(system.client, "second_voter")
    link_demo_voter("second_voter", "V0007")
    other = {"election_id": ELECTION, "preferences": [
        {"candidate_id": cid, "rank": rank} for rank, cid in enumerate(
            ("DEMO-C002", "DEMO-C001", "DEMO-C003", "DEMO-C004"), 1)]}
    assert system.client.post("/ballots/submit", json=other, headers=login(system.client, second)).status_code == 200
    close(system)
    response = count(system)
    assert response.status_code == 409 and "tie" in response.json()["detail"]
    assert result(system) is None


def test_admin_setup_preserves_voter_and_officer_separation(system):
    with pytest.raises(ValueError, match="linked voter"):
        grant("demo_voter")
    separate = register(system.client, "officer_account")
    with accounts.get_connection() as connection:
        connection.execute("UPDATE users SET role='officer' WHERE username=?", (separate["username"],))
    with pytest.raises(ValueError, match="officer"):
        grant("officer_account")
    assert system.client.get("/auth/verify", headers=system.voter).json()["role"] == "voter"


def test_admin_setup_revokes_earlier_voter_sessions(system):
    credentials = register(system.client, "new_admin")
    old_headers = login(system.client, credentials)
    grant("new_admin")
    assert system.client.get("/auth/verify", headers=old_headers).status_code == 401
    assert system.client.get("/auth/verify", headers=login(system.client, credentials)).json()["role"] == "admin"


def test_count_uses_rank_numbers_instead_of_candidate_array_order(system):
    other_ballot = {"election_id": ELECTION, "preferences": [
        {"candidate_id": f"DEMO-C00{number}", "rank": 5 - number} for number in range(1, 5)]}
    for username, voter_id in (("other_voter", "V0007"), ("third_voter", "V0008")):
        credentials = register(system.client, username)
        link_demo_voter(username, voter_id)
        assert system.client.post("/ballots/submit", json=other_ballot,
                                  headers=login(system.client, credentials)).status_code == 200
    close(system)
    counted = count(system)
    assert counted.status_code == 201
    assert counted.json()["total_ballots"] == 3
    assert counted.json()["winner_id"] == "DEMO-C004"
    assert counted.json()["rounds"][0]["totals"]["DEMO-C004"] == 2
