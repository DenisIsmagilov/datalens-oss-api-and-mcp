from unittest.mock import patch

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.testclient import TestClient

from app.auth import BearerAuthMiddleware
from app.main import create_http_app


def test_bearer_auth_middleware_is_pure_asgi():
    assert not issubclass(BearerAuthMiddleware, BaseHTTPMiddleware)


def test_protected_path_without_bearer_returns_401():
    client = TestClient(create_http_app())
    response = client.get("/mcp")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_protected_path_with_wrong_bearer_returns_401():
    client = TestClient(create_http_app())
    response = client.get(
        "/mcp", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_bearer_token_is_compared_with_compare_digest():
    with patch("app.auth.hmac.compare_digest", return_value=False) as compare_digest:
        response = TestClient(create_http_app()).get(
            "/mcp", headers={"Authorization": "Bearer test-mcp-token"}
        )

    assert response.status_code == 401
    compare_digest.assert_called_once_with(
        "Bearer test-mcp-token", "Bearer test-mcp-token"
    )


def test_protected_path_with_valid_bearer_not_401():
    with TestClient(create_http_app()) as client:
        response = client.get(
            "/mcp", headers={"Authorization": "Bearer test-mcp-token"}
        )
    assert response.status_code != 401
