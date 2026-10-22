from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_identifies_unimplemented_security():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["security_implemented"] is False

def test_sensitive_placeholders_do_not_accept_operations():
    for method, path in [("post", "/auth/login"), ("get", "/auth/verify"),
                         ("post", "/ballots"),
                         ("post", "/candidates")]:
        response = client.request(method, path)
        assert response.status_code == 501
        assert response.json()["detail"]["code"] == "NOT_IMPLEMENTED"
    # The results publication route is now implemented and must fail closed
    # when its local admin security configuration is missing.
    assert client.post("/results/demo/publish").status_code == 503
    # /eligibility/authorizations is implemented (Ved); it now fails closed with 401
    # without a verified token - see tests/eligibility/test_elig03_access.py

def test_project_pages_and_api_schema_load():
    assert client.get("/").status_code == 200
    assert client.get("/static/candidates/index.html").status_code == 200
    assert client.get("/openapi.json").status_code == 200
