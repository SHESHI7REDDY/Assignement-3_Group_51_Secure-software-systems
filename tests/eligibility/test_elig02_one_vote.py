"""ELIG-02: atomic one-vote rule and race-condition protection."""
import threading
from types import SimpleNamespace

from app.eligibility import service
from app.eligibility.repository import connect
from app.eligibility.security import Principal

OFFICER = Principal("officer-1", "officer")


def authorise(client, auth, voter="V0001"):
    return client.post("/eligibility/authorizations", json={"voter_id": voter, "channel": "ONLINE"},
                       headers=auth("voter", voter))


def test_first_authorisation_succeeds_second_is_rejected(client, auth):
    first = authorise(client, auth)
    assert first.status_code == 201 and len(first.json()["ballot_token"]) >= 40
    second = authorise(client, auth)
    assert second.status_code == 409 and second.json()["detail"] == "ALREADY_VOTED"


def test_after_voting_check_reports_already_voted(client, auth):
    authorise(client, auth)
    r = client.post("/eligibility/check", json={"voter_id": "V0001"}, headers=auth("voter", "V0001"))
    assert r.json() == {"voter_id": "V0001", "election_id": "FED-2026", "eligible": False,
                        "reason": "ALREADY_VOTED"}


def test_ineligible_voter_cannot_get_token(client, auth):
    r = client.post("/eligibility/authorizations", json={"voter_id": "V0002", "channel": "POLLING_STATION"},
                    headers=auth("officer"))
    assert r.status_code == 403


def test_concurrent_requests_issue_exactly_one_token(settings):
    """30 terminals try to authorise the same voter at the same instant."""
    n = 30
    barrier = threading.Barrier(n)
    results = []
    lock = threading.Lock()

    def attempt():
        conn = connect(settings.db_path)
        barrier.wait()
        try:
            service.authorise_to_vote(conn, settings, OFFICER, "V0007", "POLLING_STATION")
            outcome = "granted"
        except service.AlreadyVoted:
            outcome = "rejected"
        finally:
            conn.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("granted") == 1
    assert results.count("rejected") == n - 1
    conn = connect(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM ballot_tokens").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM voting_status WHERE voter_id='V0007'").fetchone()[0] == 1


def test_ballot_token_is_single_use(client, auth):
    token = authorise(client, auth).json()["ballot_token"]
    svc = auth("service", user_id="ballot-svc")
    ok = client.post("/eligibility/authorizations/redeem", json={"ballot_token": token}, headers=svc)
    assert ok.status_code == 200 and ok.json()["division"] == "Wills"
    again = client.post("/eligibility/authorizations/redeem", json={"ballot_token": token}, headers=svc)
    assert again.status_code == 409


def test_expired_token_is_rejected(client, auth, settings):
    token = authorise(client, auth).json()["ballot_token"]
    conn = connect(settings.db_path)
    conn.execute("UPDATE ballot_tokens SET expires_at = '2000-01-01T00:00:00+00:00'")
    r = client.post("/eligibility/authorizations/redeem", json={"ballot_token": token},
                    headers=auth("service", user_id="ballot-svc"))
    assert r.status_code == 409


def test_forged_token_is_rejected(client, auth):
    r = client.post("/eligibility/authorizations/redeem", json={"ballot_token": "A" * 43},
                    headers=auth("service", user_id="ballot-svc"))
    assert r.status_code == 409
