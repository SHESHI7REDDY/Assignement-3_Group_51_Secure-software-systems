"""Publication security and transition tests with isolated SQLite database."""
import sqlite3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.results.router import router
from app.results.repository import get_count
from app.results.audit import read_events, verify_audit

TOKEN = "test-admin-publish-token-long-enough"
KEY = b"audit-test-key-with-at-least-thirty-two-bytes"

@pytest.fixture
def setup_api(tmp_path, monkeypatch):
    db = tmp_path / "pub.sqlite3"
    monkeypatch.setenv("RESULTS_DB_PATH", str(db))
    monkeypatch.setenv("RESULTS_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", KEY.hex())
    api = FastAPI()
    api.include_router(router)
    return TestClient(api), db

def _count(client):
    assert client.post('/results/count', headers={'X-Results-Admin-Token':TOKEN}).status_code == 201

def _publish(client, token=TOKEN):
    return client.post('/results/DEMO-001/publish', headers={'X-Results-Admin-Token':token})

def test_publish_counted_result(setup_api):
    client, db = setup_api
    _count(client)
    response = _publish(client)
    assert response.status_code == 200
    assert response.json()['status'] == 'published'
    assert response.json()['published_at'] is not None
    assert get_count('DEMO-001', db)['status'] == 'published'

def test_audit_event_after_publication(setup_api):
    client, db = setup_api
    _count(client)
    _publish(client)
    assert [x['event_type'] for x in read_events(db)] == ['COUNT_COMPLETED','RESULT_PUBLISHED']
    assert verify_audit(KEY, db)

def test_unauthenticated_denied(setup_api):
    client, db=setup_api
    _count(client)
    assert client.post('/results/DEMO-001/publish').status_code == 401
    assert get_count('DEMO-001',db)['status']=='counted'

def test_wrong_token_denied(setup_api):
    client, db=setup_api
    _count(client)
    assert _publish(client,'wrong').status_code == 403
    assert get_count('DEMO-001',db)['status']=='counted'

def test_no_count_not_found(setup_api):
    client, _=setup_api
    assert _publish(client).status_code == 404

def test_repeat_publication_conflict(setup_api):
    client, _=setup_api
    _count(client)
    assert _publish(client).status_code == 200
    assert _publish(client).status_code == 409

def test_audit_tampering_blocks_publication(setup_api):
    client, db=setup_api
    _count(client)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE results_audit_events SET outcome='denied' WHERE sequence=1")
    assert _publish(client).status_code == 409
    assert get_count('DEMO-001',db)['status']=='counted'

def test_missing_configuration_fails_closed(setup_api, monkeypatch):
    client, db=setup_api
    _count(client)
    monkeypatch.delenv('RESULTS_ADMIN_TOKEN')
    assert _publish(client).status_code == 503
    assert get_count('DEMO-001',db)['status']=='counted'
