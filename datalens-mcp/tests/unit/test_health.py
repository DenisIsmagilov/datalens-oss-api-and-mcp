from starlette.testclient import TestClient

from app.main import create_http_app


def test_health_without_auth():
    client = TestClient(create_http_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_with_valid_bearer():
    client = TestClient(create_http_app())
    response = client.get(
        "/health", headers={"Authorization": "Bearer test-mcp-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mcp_without_auth_returns_401():
    client = TestClient(create_http_app())
    response = client.post("/mcp")
    assert response.status_code == 401


def test_mcp_with_valid_bearer_reaches_protocol_handler():
    with TestClient(create_http_app()) as client:
        response = client.post(
            "/mcp", headers={"Authorization": "Bearer test-mcp-token"}
        )
    assert response.status_code not in (401, 404)
