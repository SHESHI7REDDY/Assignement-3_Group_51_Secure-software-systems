from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_identifies_unimplemented_security():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["security_implemented"] is False


def test_sensitive_placeholders_do_not_accept_operations():
    placeholder_endpoints = [
        ("post", "/auth/login"),
        ("get", "/auth/verify"),
        ("post", "/ballots"),
        ("post", "/results/demo/publish"),
    ]

    for method, path in placeholder_endpoints:
        response = client.request(method, path)

        assert response.status_code == 501
        assert response.json()["detail"]["code"] == "NOT_IMPLEMENTED"

    # Candidate creation now requires verified authentication.
    response = client.post("/candidates")
    assert response.status_code == 401

    # Eligibility authorisation also requires verified authentication.
    response = client.post("/eligibility/authorizations")
    assert response.status_code == 401


def test_project_pages_and_api_schema_load():
    assert client.get("/").status_code == 200
    assert client.get("/static/candidates/index.html").status_code == 200
    assert client.get("/openapi.json").status_code == 200