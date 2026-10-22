"""ELIG-03: authenticated, role-based and object-level access + input validation."""
import pytest
from fastapi.testclient import TestClient


def test_missing_token_is_401(client):
    assert client.post("/eligibility/check", json={"voter_id": "V0001"}).status_code == 401


def test_tampered_token_is_401(client, auth):
    h = auth("voter", "V0001")
    body, sig = h["Authorization"][7:].split(".")
    forged = {"Authorization": f"Bearer {body}.{sig[:-2]}AA"}
    assert client.post("/eligibility/check", json={"voter_id": "V0001"}, headers=forged).status_code == 401


def test_expired_token_is_401(client, auth):
    assert client.post("/eligibility/check", json={"voter_id": "V0001"},
                       headers=auth("voter", "V0001", ttl=-5)).status_code == 401


def test_voter_cannot_read_another_voters_record(client, auth):
    """IDOR: V0001 changes the ID in the URL to V0007."""
    assert client.get("/eligibility/status/V0007", headers=auth("voter", "V0001")).status_code == 403
    assert client.post("/eligibility/check", json={"voter_id": "V0007"},
                       headers=auth("voter", "V0001")).status_code == 403


def test_voter_cannot_authorise_someone_else(client, auth):
    r = client.post("/eligibility/authorizations", json={"voter_id": "V0007", "channel": "ONLINE"},
                    headers=auth("voter", "V0001"))
    assert r.status_code == 403


def test_officer_can_read_any_record(client, auth):
    assert client.get("/eligibility/status/V0007", headers=auth("officer")).status_code == 200


@pytest.mark.parametrize("role", ["voter", "officer"])
def test_only_ballot_service_can_redeem(client, auth, role):
    r = client.post("/eligibility/authorizations/redeem", json={"ballot_token": "A" * 43}, headers=auth(role))
    assert r.status_code == 403


def test_voter_cannot_view_audit_or_approve(client, auth):
    assert client.get("/eligibility/audit/verify", headers=auth("voter")).status_code == 403
    assert client.post("/eligibility/enrolments/V0005/approve", headers=auth("voter")).status_code == 403


@pytest.mark.parametrize("bad", ["V0001' OR '1'='1", "V1;DROP TABLE electors", "<script>", "", "V12"])
def test_malformed_voter_ids_rejected(client, auth, bad):
    assert client.post("/eligibility/check", json={"voter_id": bad},
                       headers=auth("officer")).status_code == 422


def test_unexpected_fields_rejected(client, auth):
    r = client.post("/eligibility/check", json={"voter_id": "V0001", "has_voted": 0}, headers=auth("officer"))
    assert r.status_code == 422


def test_non_citizen_cannot_enrol(client, auth):
    r = client.post("/eligibility/enrol", headers=auth("officer"), json={
        "voter_id": "V0200", "full_name": "Test Person", "date_of_birth": "1990-01-01",
        "citizenship": "NZ", "state": "NSW", "division": "Sydney", "address": "1 Test St, Sydney"})
    assert r.status_code == 422


def test_self_enrolment_is_pending_until_officer_approves(client, auth):
    data = {"voter_id": "V0300", "full_name": "Ivy Tran", "date_of_birth": "1999-05-01", "citizenship": "AU",
            "state": "NSW", "division": "Sydney", "address": "10 Example St, Sydney"}
    r = client.post("/eligibility/enrol", json=data, headers=auth("voter", "V0300"))
    assert r.status_code == 201 and r.json()["enrolment_status"] == "PENDING"
    check = client.post("/eligibility/check", json={"voter_id": "V0300"}, headers=auth("voter", "V0300"))
    assert check.json()["eligible"] is False
    assert client.post("/eligibility/enrolments/V0300/approve", headers=auth("officer")).status_code == 200
    check = client.post("/eligibility/check", json={"voter_id": "V0300"}, headers=auth("voter", "V0300"))
    assert check.json()["eligible"] is True


def test_voter_can_update_own_address_only(client, auth):
    body = {"address": "99 New St, Brunswick", "division": "Wills"}
    assert client.patch("/eligibility/electors/V0001/address", json=body,
                        headers=auth("voter", "V0001")).status_code == 200
    assert client.patch("/eligibility/electors/V0007/address", json=body,
                        headers=auth("voter", "V0001")).status_code == 403


def test_security_headers_present(client):
    h = client.get("/static/eligibility/index.html").headers
    assert "default-src 'self'" in h["content-security-policy"]
    assert h["x-frame-options"] == "DENY"
    assert h["x-content-type-options"] == "nosniff"


def test_integrated_app_has_no_mock_login_and_fails_closed():
    """The shared app (app/main.py) must not expose the dev login, and must
    reject eligibility calls without a token verified by the Auth module."""
    from app.main import app as integrated
    c = TestClient(integrated)
    assert c.post("/dev/mock-token", json={"user_id": "x1", "role": "officer"}).status_code == 404
    assert c.post("/eligibility/authorizations",
                  json={"voter_id": "V0001", "channel": "ONLINE"}).status_code == 401


def test_integrated_app_rejects_mock_tokens_when_mock_auth_off(auth):
    from app.main import app as integrated
    c = TestClient(integrated)
    r = c.post("/eligibility/check", json={"voter_id": "V0001"}, headers=auth("officer"))
    assert r.status_code in (401, 503)
