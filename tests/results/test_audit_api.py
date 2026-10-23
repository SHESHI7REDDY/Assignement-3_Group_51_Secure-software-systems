"""Security tests for the local administrative audit API."""
import sqlite3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.results.audit import append_event
from app.results.router import router

KEY = b"safe-testing-only-hmac-key-of-32bytes-long"
TOKEN = "safe-local-demo-administrator-token"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "audit_api.sqlite3"
    monkeypatch.setenv("RESULTS_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("RESULTS_DB_PATH", str(db))
    append_event("DEMO-001", "COUNT_COMPLETED", "test-actor", "success", KEY, db)
    append_event("DEMO-002", "COUNT_COMPLETED", "test-actor", "success", KEY, db)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), db


def test_get_audit_success(client):
    api, _ = client
    r = api.get("/results/DEMO-001/audit", headers={"X-Results-Admin-Token": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["event_type"] == "COUNT_COMPLETED"
    assert "actor_id" not in data["events"][0]


def test_global_chain_verification(client):
    api, _ = client
    response = api.get("/results/DEMO-001/audit/verify", headers={"X-Results-Admin-Token": TOKEN})
    assert response.status_code == 200
    assert response.json()["integrity_valid"] is True
    assert response.json()["scope"] == "global_chain"
    assert response.json()["events_for_election"] == 1


@pytest.mark.parametrize("endpoint", ["/results/DEMO-001/audit", "/results/DEMO-001/audit/verify"])
def test_anonymous_forbidden(client, endpoint):
    api, _ = client
    assert api.get(endpoint).status_code == 401


@pytest.mark.parametrize("endpoint", ["/results/DEMO-001/audit", "/results/DEMO-001/audit/verify"])
def test_invalid_token_forbidden(client, endpoint):
    api, _ = client
    assert api.get(endpoint, headers={"X-Results-Admin-Token": "wrong"}).status_code == 403


def test_tampering_blocks_event_reads(client):
    api, db = client
    with sqlite3.connect(db) as con:
        con.execute("UPDATE results_audit_events SET outcome='failure' WHERE sequence=1")
    r = api.get("/results/DEMO-001/audit", headers={"X-Results-Admin-Token": TOKEN})
    assert r.status_code == 409
    verify = api.get("/results/DEMO-001/audit/verify", headers={"X-Results-Admin-Token": TOKEN})
    assert verify.json()["integrity_valid"] is False


def test_invalid_configuration_fails_closed(client, monkeypatch):
    api, _ = client
    monkeypatch.delenv("RESULTS_AUDIT_HMAC_KEY")
    response = api.get("/results/DEMO-001/audit", headers={"X-Results-Admin-Token": TOKEN})
    assert response.status_code == 503
