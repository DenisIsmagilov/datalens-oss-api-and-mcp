import logging

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app
from app.request_context import accept_request_id

AUTH = "http://auth.example:8080"
CONTROL = "http://control-api.example:8080"


def _client() -> TestClient:
    return TestClient(create_app())


def test_incoming_request_id_is_echoed():
    response = _client().get("/health", headers={"x-request-id": "trace-abc.1"})
    assert response.headers["x-request-id"] == "trace-abc.1"


def test_request_id_is_generated_when_missing():
    response = _client().get("/health")
    assert len(response.headers["x-request-id"]) == 32


def test_unsafe_request_id_is_replaced():
    response = _client().get("/health", headers={"x-request-id": "bad id with spaces"})
    assert response.headers["x-request-id"] != "bad id with spaces"
    assert len(response.headers["x-request-id"]) == 32


def test_accept_request_id_rejects_trailing_newline():
    result = accept_request_id("abc\n")
    assert result != "abc\n"
    assert len(result) == 32


def test_request_id_on_unhandled_500(caplog):
    caplog.set_level(logging.ERROR, logger="datalens_api.errors")
    app = create_app()

    @app.get("/__boom")
    def _boom() -> None:
        raise RuntimeError("boom")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/__boom",
        headers={"x-request-id": "trace-500"},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert response.headers["x-request-id"] == "trace-500"
    error_records = [
        r
        for r in caplog.records
        if r.name == "datalens_api.errors" and r.levelno == logging.ERROR
    ]
    assert any("trace-500" in r.getMessage() for r in error_records)
    assert any(r.exc_info is not None for r in error_records)


@respx.mock
def test_request_id_reaches_backend_and_error_response():
    respx.post(f"{AUTH}/signin").mock(
        return_value=httpx.Response(200, json={"accessToken": "jwt"})
    )
    route = respx.get(f"{CONTROL}/api/v1/datasets/ds1/versions/draft").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    response = _client().post(
        "/rpc/getDataset",
        json={"datasetId": "ds1"},
        headers={"Authorization": "Bearer test-dl-api-token", "x-request-id": "trace-xyz"},
    )
    assert response.status_code == 404
    assert route.calls[0].request.headers["x-request-id"] == "trace-xyz"
    assert response.headers["x-request-id"] == "trace-xyz"
