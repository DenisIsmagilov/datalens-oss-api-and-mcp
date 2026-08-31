from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_missing_bearer_is_401():
    response = _client().post("/rpc/definitelyMissing", json={})
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHENTICATED"


def test_wrong_bearer_is_401():
    response = _client().post(
        "/rpc/definitelyMissing",
        json={},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_unsupported_api_version_is_400():
    response = _client().post(
        "/rpc/definitelyMissing",
        json={},
        headers={
            "Authorization": "Bearer test-dl-api-token",
            "x-dl-api-version": "1",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_ARGUMENT"
