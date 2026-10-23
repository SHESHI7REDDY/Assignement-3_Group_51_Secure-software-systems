"""Read-only published results API contract and privacy regression tests."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.results.router import router
from app.results.repository import get_count

TOKEN = 'fixture-admin-token-long-enough'
KEY = b'fixture-secret-key-at-least-32-bytes!'
ELECTION = 'DEMO-001'


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = tmp_path / 'read.sqlite3'
    monkeypatch.setenv('RESULTS_DB_PATH', str(db))
    monkeypatch.setenv('RESULTS_ADMIN_TOKEN', TOKEN)
    monkeypatch.setenv('RESULTS_AUDIT_HMAC_KEY', KEY.hex())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    return client, db


def _count(client):
    resp = client.post('/results/count', headers={'X-Results-Admin-Token': TOKEN})
    assert resp.status_code == 201


def _publish(client):
    resp = client.post(f'/results/{ELECTION}/publish', headers={'X-Results-Admin-Token': TOKEN})
    assert resp.status_code == 200


def test_missing_election_is_not_found(api):
    client, _ = api
    r = client.get('/results/DOES-NOT-EXIST')
    assert r.status_code == 404
    assert r.json()['detail'] == 'Published result not found'


def test_counted_result_is_not_public(api):
    client, _ = api
    _count(client)
    r = client.get(f'/results/{ELECTION}')
    assert r.status_code == 404
    assert r.json()['detail'] == 'Published result not found'


def test_published_result_is_public(api):
    client, _ = api
    _count(client)
    _publish(client)
    r = client.get(f'/results/{ELECTION}')
    assert r.status_code == 200
    payload = r.json()
    assert payload['election_id'] == ELECTION
    assert payload['winner_id'] == 'CAND-A'
    assert payload['total_ballots'] == 10
    assert payload['status'] == 'published'
    assert payload['published_at']
    assert len(payload['rounds']) == 2


def test_public_response_leaks_no_ballots_or_credentials(api):
    client, _ = api
    _count(client)
    _publish(client)
    payload = client.get(f'/results/{ELECTION}').json()
    assert set(payload) == {'election_id', 'winner_id', 'status', 'total_ballots', 'rounds', 'published_at'}
    as_text = str(payload).lower()
    for word in ('ballot_id', 'voter_id', 'password', 'token', 'hmac', 'secret', 'counted_at'):
        assert word not in as_text


def test_public_read_does_not_mutate_stored_record(api):
    client, db = api
    _count(client)
    _publish(client)
    before = get_count(ELECTION, db)
    for _ in range(3):
        assert client.get(f'/results/{ELECTION}').status_code == 200
    assert get_count(ELECTION, db) == before


def test_absent_and_unpublished_have_same_response(api):
    client, _ = api
    _count(client)
    a = client.get(f'/results/{ELECTION}')
    b = client.get('/results/MISSING')
    assert (a.status_code, a.json()) == (b.status_code, b.json())


def test_read_route_is_get_only(api):
    client, _ = api
    r = client.put('/results/DEMO-001')
    assert r.status_code == 405


def test_request_does_not_require_admin_token_after_publish(api):
    client, _ = api
    _count(client)
    _publish(client)
    assert client.get(f'/results/{ELECTION}').status_code == 200
