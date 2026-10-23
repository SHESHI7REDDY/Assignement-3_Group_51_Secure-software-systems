"""Tests for the fictional count API and security boundaries."""
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.results.router import router
from app.results.repository import get_count
from app.results.audit import read_events, verify_audit

TOKEN = "test-results-admin-token-very-long"
KEY = b"test-only-hmac-key-with-more-than-32-bytes"


@pytest.fixture
def setup_api(tmp_path, monkeypatch):
    db = tmp_path / "count_api.sqlite3"
    monkeypatch.setenv("RESULTS_DB_PATH", str(db))
    monkeypatch.setenv("RESULTS_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", KEY.hex())
    api = FastAPI()
    api.include_router(router)
    return TestClient(api), db


def test_fictional_count_api(setup_api):
    client, db = setup_api
    response = client.post("/results/count", headers={"X-Results-Admin-Token": TOKEN})
    assert response.status_code == 201
    data = response.json()
    assert data["winner_id"] == "CAND-A"
    assert data["total_ballots"] == 10
    assert data["rounds"][0]["totals"] == {"CAND-A": 4, "CAND-B": 4, "CAND-C": 2}
    assert data["rounds"][1]["totals"] == {"CAND-A": 6, "CAND-B": 4}
    assert get_count("DEMO-001", db)["winner_id"] == "CAND-A"
    assert verify_audit(KEY, db)
    assert read_events(db, election_id="DEMO-001")[0]["event_type"] == "COUNT_COMPLETED"


def test_duplicate_count_rejected(setup_api):
    client, _ = setup_api
    headers = {"X-Results-Admin-Token": TOKEN}
    assert client.post("/results/count", headers=headers).status_code == 201
    assert client.post("/results/count", headers=headers).status_code == 409


def test_anonymous_rejected(setup_api):
    client, _ = setup_api
    assert client.post("/results/count").status_code == 401


def test_invalid_admin_rejected(setup_api):
    client, _ = setup_api
    assert client.post("/results/count", headers={"X-Results-Admin-Token": "wrong"}).status_code == 403


def test_missing_key_fails_closed(setup_api, monkeypatch):
    client, _ = setup_api
    monkeypatch.delenv("RESULTS_AUDIT_HMAC_KEY")
    assert client.post("/results/count", headers={"X-Results-Admin-Token": TOKEN}).status_code == 503


def test_existing_invalid_audit_blocks_count(setup_api):
    client, db = setup_api
    from app.results.audit import append_event
    import sqlite3
    append_event("DEMO-002", "COUNT_STARTED", "tester", "success", KEY, db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE results_audit_events SET outcome = 'failure' WHERE sequence = 1")
    assert client.post("/results/count", headers={"X-Results-Admin-Token": TOKEN}).status_code == 409
    assert get_count("DEMO-001", db) is None
