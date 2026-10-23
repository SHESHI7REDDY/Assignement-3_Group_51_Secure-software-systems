"""Real login -> linked voter -> eligibility -> encrypted ballot, using temp data."""
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import date

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import repository as accounts
from app.auth.profiles import initialise_profiles, link_demo_voter
from app.auth.router import router as auth_router
from app.auth.sessions import hash_token
from app.ballot import integration, repository, service
from app.ballot.lifecycle import transition
from app.ballot.router import router
from app.candidates.repository import get_connection
from app.candidates.seed import seed_demo
from app.eligibility import audit, repository as roll
from app.eligibility.config import Settings, get_settings
from app.eligibility.router import router as eligibility_router
from app.eligibility.security import Principal, get_principal

ELECTION = "DEMO-A3-ELECTIONS"
BODY = {"election_id": ELECTION, "preferences": [
    {"candidate_id": f"DEMO-C00{rank}", "rank": rank} for rank in range(1, 5)
]}


@dataclass
class Demo:
    client: TestClient
    headers: dict
    settings: Settings
    candidates: object
    key: object

    def query(self, sql, params=()):
        with closing(roll.connect(self.settings.db_path)) as connection:
            return connection.execute(sql, params).fetchall()

    def assert_unused(self):
        assert not self.query("SELECT * FROM voting_status WHERE voter_id = 'V0001'")
        assert not self.query("SELECT * FROM accepted_ballots")
        assert not self.query("SELECT * FROM ballot_tokens")
        assert not self.query("SELECT * FROM audit_log")


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "DB_PATH", tmp_path / "users.db")
    key = tmp_path / "ballot.key"
    monkeypatch.setenv("BALLOT_KEY_FILE", str(key))
    initialise_profiles()
    settings = Settings(db_path=str(tmp_path / "roll.db"), election_id=ELECTION,
                        election_date=date(2026, 12, 5), mock_auth=False,
                        auth_secret="test-only-secret", pseudonym_key="test-only-pseudonym")
    roll.seed(settings)  # Tests only: isolated roll, never a developer's database.
    candidates = tmp_path / "candidates.db"
    seed_demo(candidates)
    transition(ELECTION, "OPEN", candidates)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(eligibility_router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[integration.get_candidate_db_path] = lambda: candidates
    with TestClient(app) as client:
        credentials = {"username": "demo_voter", "password": "FictionalPassword123"}
        assert client.post("/auth/register", json=credentials).status_code == 201
        link_demo_voter("demo_voter", "V0001")
        login = client.post("/auth/login", json=credentials)
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        yield Demo(client, headers, settings, candidates, key)


def test_real_login_accepts_one_ballot_and_encrypts_choices(demo):
    response = demo.client.post("/ballots/submit", json=BODY, headers=demo.headers)
    assert response.status_code == 200
    rows = demo.query("SELECT * FROM accepted_ballots")
    assert len(rows) == 1
    assert rows[0]["ballot_id"] == response.json()["ballot_id"]
    assert len(rows[0]["ballot_id"]) == 32
    assert set(rows[0].keys()) == {"ballot_id", "election_id", "encrypted_ballot"}
    ciphertext = rows[0]["encrypted_ballot"]
    assert "DEMO-C001" not in ciphertext and "preferences" not in ciphertext
    decrypted = json.loads(Fernet(demo.key.read_bytes()).decrypt(ciphertext.encode()))
    assert decrypted == {"preferences": BODY["preferences"]}
    assert "voter_id" not in decrypted
    assert demo.query("SELECT has_voted FROM voting_status WHERE voter_id = 'V0001'")[0][0] == 1
    assert demo.query("SELECT redeemed FROM ballot_tokens")[0][0] == 1
    with closing(roll.connect(demo.settings.db_path)) as connection:
        assert audit.verify_chain(connection)["valid"] is True
    assert demo.key.stat().st_mode & 0o777 == 0o600


def test_duplicate_submission_does_not_create_another_ballot(demo):
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 200
    response = demo.client.post("/ballots/submit", json=BODY, headers=demo.headers)
    assert response.status_code == 409 and response.json()["detail"] == "ALREADY_VOTED"
    assert len(demo.query("SELECT * FROM accepted_ballots")) == 1
    assert len(demo.query("SELECT * FROM ballot_tokens")) == 1


def test_old_mock_headers_do_not_grant_access(demo):
    response = demo.client.post("/ballots/submit", json=BODY,
                               headers={"X-Auth-Token": "ballot-demo-token", "X-Mock-Role": "voter"})
    assert response.status_code == 401
    assert not demo.query("SELECT * FROM voting_status WHERE voter_id = 'V0001'")


@pytest.mark.parametrize("mode", ["missing", "invalid", "expired", "revoked"])
def test_invalid_sessions_cannot_vote(demo, mode):
    headers = demo.headers
    if mode == "missing":
        headers = {}
    elif mode == "invalid":
        headers = {"Authorization": "Bearer invalid-token"}
    elif mode == "revoked":
        assert demo.client.post("/auth/logout", headers=headers).status_code == 200
    else:
        with accounts.get_connection() as connection:
            connection.execute("UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
                               (int(time.time()) - 10, hash_token(headers["Authorization"][7:])))
    assert demo.client.post("/ballots/submit", json=BODY, headers=headers).status_code == 401


def test_non_voter_cannot_vote_even_with_voter_header(demo):
    with accounts.get_connection() as connection:
        connection.execute("UPDATE users SET role = 'officer' WHERE username = 'demo_voter'")
    response = demo.client.post("/ballots/submit", json=BODY,
                               headers={**demo.headers, "X-Mock-Role": "voter"})
    assert response.status_code == 403


def test_unlinked_account_cannot_choose_voter_id_in_headers(demo):
    with accounts.get_connection() as connection:
        connection.execute("DELETE FROM account_voters")
    response = demo.client.post("/ballots/submit", json=BODY,
                               headers={**demo.headers, "X-Voter-ID": "V0001"})
    assert response.status_code == 403


@pytest.mark.parametrize("change,status", [
    ("duplicate_rank", 400), ("duplicate_candidate", 400), ("foreign_candidate", 400),
    ("missing_candidate", 400), ("wrong_election", 400), ("extra_identity", 422),
    ("string_rank", 422), ("boolean_rank", 422), ("extra_preference_field", 422),
])
def test_invalid_ballots_do_not_use_voting_right(demo, change, status):
    body = copy.deepcopy(BODY)
    if change == "duplicate_rank": body["preferences"][1]["rank"] = 1
    elif change == "duplicate_candidate": body["preferences"][1]["candidate_id"] = "DEMO-C001"
    elif change == "foreign_candidate": body["preferences"][1]["candidate_id"] = "CAND-001"
    elif change == "missing_candidate": body["preferences"].pop()
    elif change == "wrong_election": body["election_id"] = "OTHER-2026"
    elif change == "extra_identity": body["voter_id"] = "V0007"
    elif change == "string_rank": body["preferences"][0]["rank"] = "1"
    elif change == "boolean_rank": body["preferences"][0]["rank"] = True
    else: body["preferences"][0]["voter_id"] = "V0007"
    assert demo.client.post("/ballots/submit", json=body, headers=demo.headers).status_code == status
    assert not demo.query("SELECT * FROM voting_status WHERE voter_id = 'V0001'")
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 200


@pytest.mark.parametrize("state", ["DRAFT", "CLOSED"])
def test_only_open_elections_accept_votes(demo, state):
    with closing(get_connection(demo.candidates)) as connection:
        with connection:
            connection.execute("UPDATE elections SET status = ?", (state,))
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 409
    demo.assert_unused()


def test_catalog_uses_real_active_candidates(demo):
    with closing(get_connection(demo.candidates)) as connection:
        with connection:
            connection.execute("UPDATE candidates SET active = 0 WHERE candidate_id = 'DEMO-C004'")
    catalog = demo.client.get("/ballots/candidates").json()
    assert catalog["election_id"] == ELECTION and catalog["status"] == "OPEN"
    assert [row["name"] for row in catalog["candidates"]] == ["Varshil", "Ved", "Akshit"]
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 400
    body = copy.deepcopy(BODY)
    body["preferences"].pop()
    assert demo.client.post("/ballots/submit", json=body, headers=demo.headers).status_code == 200


def test_ineligible_roll_record_is_rechecked(demo):
    with closing(roll.connect(demo.settings.db_path)) as connection:
        connection.execute("UPDATE electors SET disqualified = 1 WHERE voter_id = 'V0001'")
    response = demo.client.post("/ballots/submit", json=BODY, headers=demo.headers)
    assert response.status_code == 403 and response.json()["detail"] == "NOT_ELIGIBLE"
    demo.assert_unused()


@pytest.mark.parametrize("failure", ["encryption", "storage", "audit", "redemption"])
def test_failure_rolls_back_everything_and_allows_retry(demo, monkeypatch, failure):
    def broken(*args, **kwargs):
        raise RuntimeError("Simulated internal failure")
    with monkeypatch.context() as patch:
        if failure == "encryption": patch.setattr(service, "encrypt_ballot", broken)
        elif failure == "storage": patch.setattr(repository, "save_ballot", broken)
        elif failure == "audit": patch.setattr(audit, "append", broken)
        else: patch.setattr(integration.eligibility, "redeem_token", lambda *args, **kwargs: None)
        response = demo.client.post("/ballots/submit", json=BODY, headers=demo.headers)
        assert response.status_code == 503
        assert "Simulated" not in response.text
    demo.assert_unused()
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 200


def test_two_concurrent_submissions_accept_exactly_one(demo):
    def submit(_):
        return demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(submit, range(2)))
    assert sorted(statuses) == [200, 409]
    assert len(demo.query("SELECT * FROM accepted_ballots")) == 1
    assert len(demo.query("SELECT * FROM ballot_tokens")) == 1


def test_lost_key_is_not_replaced_after_a_vote(demo):
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 200
    demo.key.unlink()
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 503
    assert not demo.key.exists()
    assert len(demo.query("SELECT * FROM accepted_ballots")) == 1


def test_validation_does_not_mark_voted(demo):
    assert demo.client.post("/ballots/validate", json=BODY, headers=demo.headers).status_code == 200
    demo.assert_unused()


def test_direct_real_authorisation_cannot_consume_vote_without_ballot(demo):
    # Bypass the remote verifier only for this route test; ballot routes still
    # authenticate the real session. The real-mode API must reject issuance.
    demo.client.app.dependency_overrides[get_principal] = lambda: Principal("1", "voter", "V0001")
    response = demo.client.post("/eligibility/authorizations",
                               json={"voter_id": "V0001", "channel": "ONLINE"}, headers=demo.headers)
    assert response.status_code == 409
    assert not demo.query("SELECT * FROM voting_status WHERE voter_id = 'V0001'")


def test_closed_election_cannot_be_reopened(demo):
    transition(ELECTION, "CLOSED", demo.candidates)
    with pytest.raises(ValueError):
        transition(ELECTION, "OPEN", demo.candidates)
    with closing(get_connection(demo.candidates)) as connection:
        assert connection.execute("SELECT status FROM elections").fetchone()[0] == "CLOSED"


def test_election_state_cannot_change_during_ballot_transaction(demo, monkeypatch):
    import sqlite3

    encrypt = service.encrypt_ballot

    def check_lock_then_encrypt(ballot, cipher):
        with closing(sqlite3.connect(demo.candidates, timeout=0.05)) as other:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("UPDATE elections SET status = 'CLOSED' WHERE election_id = ?", (ELECTION,))
        return encrypt(ballot, cipher)

    monkeypatch.setattr(service, "encrypt_ballot", check_lock_then_encrypt)
    assert demo.client.post("/ballots/submit", json=BODY, headers=demo.headers).status_code == 200
    transition(ELECTION, "CLOSED", demo.candidates)
    assert demo.client.get("/ballots/candidates").json()["status"] == "CLOSED"
