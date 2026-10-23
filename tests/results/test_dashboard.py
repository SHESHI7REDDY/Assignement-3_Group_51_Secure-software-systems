from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.shared.config import FRONTEND


def test_dashboard_is_served_from_existing_static_mount():
    response = TestClient(app).get('/static/results/index.html')
    assert response.status_code == 200
    assert 'Counting, Results &amp; Audit' in response.text
    assert 'Not implemented. This page is a development placeholder.' not in response.text


def test_dashboard_has_accessible_controls():
    html = (FRONTEND / 'results' / 'index.html').read_text(encoding='utf-8')
    for identifier in ('lookup-form', 'election', 'public-result', 'admin-login', 'admin-username', 'admin-password',
                       'count-button', 'publish-button', 'verify-button', 'events-button'):
        assert f'id="{identifier}"' in html


def test_dashboard_assets_are_served():
    client = TestClient(app)
    assert client.get('/static/results/dashboard.js').status_code == 200
    assert client.get('/static/results/results.css').status_code == 200


def test_dashboard_uses_same_origin_and_no_browser_storage_for_token():
    js = (FRONTEND / 'results' / 'dashboard.js').read_text(encoding='utf-8')
    assert 'Authorization' in js
    assert 'X-Results-Admin-Token' not in js
    assert '/auth/login' in js
    assert 'localStorage' not in js
    assert 'sessionStorage' not in js
    assert 'innerHTML' not in js
    assert 'http://' not in js and 'https://' not in js


def test_dashboard_fetches_public_result_and_protected_actions():
    js = (FRONTEND / 'results' / 'dashboard.js').read_text(encoding='utf-8')
    assert '/results/${pathId()}' in js
    assert '/results/count' in js
    assert 'audit/verify' in js
    assert 'audit`' in js
