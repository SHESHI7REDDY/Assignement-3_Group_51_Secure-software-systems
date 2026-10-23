"""End-to-end security regression tests for the local fictional election.

All data and credentials are isolated per test; no external election service is used.
"""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.results.router import router
from app.results.audit import verify_audit
from app.results.repository import get_count

TOKEN = "demo-e2e-admin-token-32-characters"
KEY = b"e2e-test-hmac-key-32-bytes-minimum-1234"


@pytest.fixture
def system(tmp_path, monkeypatch):
    db = tmp_path / "results_e2e.sqlite3"
    monkeypatch.setenv("RESULTS_DB_PATH", str(db))
    monkeypatch.setenv("RESULTS_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", KEY.hex())
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client, db


def auth():
    return {"X-Results-Admin-Token": TOKEN}


def test_complete_count_publish_read_and_audit(system):
    client, db = system
    count = client.post("/results/count", headers=auth())
    assert count.status_code == 201
    assert count.json()["winner_id"] == "CAND-A"
    assert count.json()["total_ballots"] == 10
    rounds = count.json()["rounds"]
    assert rounds[0]["totals"] == {"CAND-A": 4, "CAND-B": 4, "CAND-C": 2}
    assert rounds[-1]["totals"] == {"CAND-A": 6, "CAND-B": 4}
    assert client.get("/results/DEMO-001").status_code == 404
    published = client.post("/results/DEMO-001/publish", headers=auth())
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    public = client.get("/results/DEMO-001")
    assert public.status_code == 200
    data = public.json()
    assert data["winner_id"] == "CAND-A"
    assert data["total_ballots"] == 10
    assert "ballots" not in data and "voter_id" not in data
    assert client.get("/results/DEMO-001/audit/verify", headers=auth()).json()["integrity_valid"] is True
    events = client.get("/results/DEMO-001/audit", headers=auth())
    assert events.status_code == 200
    assert [e["event_type"] for e in events.json()["events"]] == ["COUNT_COMPLETED", "RESULT_PUBLISHED"]
    assert verify_audit(KEY, db)


def test_unauthorized_actions_do_not_mutate_results(system):
    client, db = system
    assert client.post("/results/count").status_code == 401
    assert client.post("/results/count", headers={"X-Results-Admin-Token": "voter"}).status_code == 403
    assert get_count("DEMO-001", db) is None
    assert client.post("/results/count", headers=auth()).status_code == 201
    assert client.post("/results/DEMO-001/publish").status_code == 401
    assert client.post("/results/DEMO-001/publish", headers={"X-Results-Admin-Token": "voter"}).status_code == 403
    assert get_count("DEMO-001", db)["status"] == "counted"


def test_duplicate_count_and_publish_are_rejected(system):
    client, db = system
    assert client.post("/results/count", headers=auth()).status_code == 201
    assert client.post("/results/count", headers=auth()).status_code == 409
    assert client.post("/results/DEMO-001/publish", headers=auth()).status_code == 200
    assert client.post("/results/DEMO-001/publish", headers=auth()).status_code == 409
    assert get_count("DEMO-001", db)["status"] == "published"


def test_tampering_blocks_publication_and_audit_read(system):
    client, db = system
    assert client.post("/results/count", headers=auth()).status_code == 201
    with sqlite3.connect(db) as con:
        con.execute("UPDATE results_audit_events SET outcome='altered' WHERE sequence=1")
    assert client.get("/results/DEMO-001/audit/verify", headers=auth()).json()["integrity_valid"] is False
    assert client.get("/results/DEMO-001/audit", headers=auth()).status_code == 409
    assert client.post("/results/DEMO-001/publish", headers=auth()).status_code == 409
    assert get_count("DEMO-001", db)["status"] == "counted"


def test_public_endpoint_is_read_only(system):
    client, _ = system
    assert client.post("/results/count", headers=auth()).status_code == 201
    assert client.post("/results/DEMO-001/publish", headers=auth()).status_code == 200
    assert client.put("/results/DEMO-001", json={"winner_id": "CAND-C"}).status_code == 405
    assert client.get("/results/DEMO-001").json()["winner_id"] == "CAND-A"


def test_wrong_election_cannot_be_published(system):
    client, _ = system
    assert client.post("/results/count", headers=auth()).status_code == 201
    assert client.post("/results/OTHER/publish", headers=auth()).status_code == 404
    assert client.get("/results/OTHER").status_code == 404
