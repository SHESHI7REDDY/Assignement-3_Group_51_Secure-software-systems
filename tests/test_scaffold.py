"""Checks for the combined application and protected endpoints."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_application_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authentication_requires_credentials():
    response = client.get("/auth/verify")

    assert response.status_code == 401


def test_login_rejects_missing_fields():
    response = client.post("/auth/login", json={})

    assert response.status_code == 422


def test_candidate_creation_requires_authentication():
    response = client.post(
        "/candidates",
        json={
            "election_id": "DEMO-A3-ELECTIONS",
            "name": "Demonstration Candidate",
            "party": "Independent",
            "ballot_order": 5,
        },
    )

    assert response.status_code == 401


def test_eligibility_authorisation_requires_authentication():
    response = client.post(
        "/eligibility/authorizations",
        json={
            "voter_id": "V0001",
            "channel": "ONLINE",
        },
    )

    assert response.status_code == 401


def test_ballot_submission_requires_authentication():
    response = client.post(
        "/ballots/submit",
        json={
            "election_id": "ELECTION-2026",
            "preferences": [
                {"candidate_id": "CAND-001", "rank": 1},
                {"candidate_id": "CAND-002", "rank": 2},
                {"candidate_id": "CAND-003", "rank": 3},
                {"candidate_id": "CAND-004", "rank": 4},
            ],
        },
    )

    assert response.status_code == 401


def test_results_counting_requires_administrator_credentials(
    monkeypatch,
):
    # These values configure this test only.
    monkeypatch.setenv(
        "RESULTS_ADMIN_TOKEN",
        "test-only-administrator-credential",
    )
    monkeypatch.setenv(
        "RESULTS_AUDIT_HMAC_KEY",
        "ab" * 32,
    )

    response = client.post("/results/count")

    assert response.status_code == 401


def test_project_pages_and_api_schema_load():
    paths = [
        "/",
        "/static/auth.html",
        "/static/candidates/index.html",
        "/static/eligibility/index.html",
        "/static/ballot/index.html",
        "/static/results/index.html",
        "/openapi.json",
    ]

    for path in paths:
        response = client.get(path)

        assert response.status_code == 200, path