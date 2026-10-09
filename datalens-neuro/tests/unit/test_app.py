import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import get_settings
from app.errors import register_exception_handlers
from app.main import create_app


def test_health_ok():
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["enabled"] is True


def test_health_reports_disabled(monkeypatch):
    monkeypatch.setenv("NEURO_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["enabled"] is False


def test_request_id_is_echoed_and_generated():
    with TestClient(create_app()) as client:
        echoed = client.get("/health", headers={"x-request-id": "trace-1"})
        generated = client.get("/health", headers={"x-request-id": "bad id!"})
    assert echoed.headers["x-request-id"] == "trace-1"
    assert generated.headers["x-request-id"] != "bad id!"
    assert len(generated.headers["x-request-id"]) == 32


def test_unhandled_error_is_generic_500_with_request_id():
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"x-request-id": "trace-2"})
    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL", "message": "Internal error", "details": {}}
    assert response.headers["x-request-id"] == "trace-2"


def test_validation_error_hides_input():
    app = FastAPI()
    register_exception_handlers(app)

    class Body(BaseModel):
        value: int

    @app.post("/echo")
    async def echo(body: Body):
        return body

    response = TestClient(app).post("/echo", json={"value": "секрет"})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_ARGUMENT"
    assert "секрет" not in response.text


def test_unknown_route_and_method_use_error_format():
    with TestClient(create_app()) as client:
        missing = client.get("/nope", headers={"x-request-id": "trace-404"})
        wrong_method = client.get("/v1/chat")
    assert missing.status_code == 404
    assert missing.json() == {"code": "NOT_FOUND", "message": "Not Found", "details": {}}
    assert missing.headers["x-request-id"] == "trace-404"
    assert wrong_method.status_code == 405
    assert wrong_method.json()["code"] == "METHOD_NOT_ALLOWED"
    assert wrong_method.headers["allow"] == "POST"
    assert "x-request-id" in wrong_method.headers


def test_llm_client_is_closed_on_shutdown():
    class ClosableLLM:
        closed = False

        async def aclose(self):
            self.closed = True

    llm = ClosableLLM()
    with TestClient(create_app(llm_factory=lambda _settings: llm)):
        assert not llm.closed
    assert llm.closed


def test_health_reports_default_pack_and_startup_warnings(monkeypatch, caplog):
    monkeypatch.setenv("NEURO_API_TOKEN", "")
    monkeypatch.setenv("NEURO_DEFAULT_PACK", "absent-pack")
    get_settings.cache_clear()
    with caplog.at_level(logging.WARNING, logger="datalens_neuro.startup"):
        with TestClient(create_app(llm_factory=lambda _settings: None)) as client:
            response = client.get("/health")
    assert response.status_code == 200 and response.json()["defaultPack"] == "missing"
    assert "NEURO_API_TOKEN is empty" in caplog.text
    assert "LLM is not configured" in caplog.text
    assert "default pack is missing" in caplog.text
    assert "test-llm-key" not in caplog.text


def test_no_startup_warnings_when_configured(caplog):
    with caplog.at_level(logging.WARNING, logger="datalens_neuro.startup"):
        with TestClient(create_app()):
            pass
    assert [r for r in caplog.records if r.name == "datalens_neuro.startup"] == []
