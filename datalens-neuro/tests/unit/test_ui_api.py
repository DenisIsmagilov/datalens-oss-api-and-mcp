import json
import time
from urllib.parse import quote

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from tests.fakes import ScriptedLLM, text

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = PRIVATE.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
ORIGIN = "http://127.0.0.1:8080"


def _token(roles=("datalens.admin",), exp=None, algorithm="RS256"):
    payload = {"userId": "u1", "roles": list(roles), "exp": exp or int(time.time()) + 60}
    key = "secret" if algorithm == "HS256" else PRIVATE
    return jwt.encode(payload, key, algorithm=algorithm)


def _headers(token=None, origin=ORIGIN):
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if token is not None:
        raw = quote(json.dumps({"accessToken": token}))
        headers["Cookie"] = "auth=" + raw
    return headers


def _enable(monkeypatch, **extra):
    monkeypatch.setenv("NEURO_UI_ENABLED", "true")
    monkeypatch.setenv("AUTH_TOKEN_PUBLIC_KEY", PUBLIC)
    monkeypatch.setenv("NEURO_UI_ORIGINS", ORIGIN)
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _client(llm=None) -> TestClient:
    llm = llm or ScriptedLLM([])
    return TestClient(create_app(llm_factory=lambda _settings: llm))


def test_session_hides_when_ui_disabled():
    with _client() as client:
        response = client.get("/v1/ui/session", headers=_headers(_token()))
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_session_disabled_neuro(monkeypatch):
    _enable(monkeypatch, NEURO_ENABLED="false")
    with _client() as client:
        session = client.get("/v1/ui/session")
        thread = client.get("/v1/ui/thread")
        chat = client.post("/v1/ui/chat", json={"message": "q"})
    assert session.status_code == 200 and session.json() == {"enabled": False}
    assert thread.status_code == 200 and thread.json() == {"enabled": False}
    assert chat.status_code == 503 and chat.json()["code"] == "NEURO_DISABLED"


def test_session_roles_and_origin(monkeypatch):
    _enable(monkeypatch)
    with _client() as client:
        viewer = client.get("/v1/ui/session", headers=_headers(_token(roles=["datalens.viewer"])))
        no_origin = client.get("/v1/ui/session", headers=_headers(_token(), origin=None))
        evil = client.get("/v1/ui/session", headers=_headers(_token(), origin="http://evil"))
        ok = client.get("/v1/ui/session", headers=_headers(_token()))
        ps256 = client.get("/v1/ui/session", headers=_headers(_token(algorithm="PS256")))
        expired = client.get("/v1/ui/session", headers=_headers(_token(exp=int(time.time()) - 10)))
        hs256 = client.get("/v1/ui/session", headers=_headers(_token(algorithm="HS256")))
        empty_cookie = client.get("/v1/ui/session", headers={"Origin": ORIGIN, "Cookie": "auth={}"})
        no_cookie = client.get("/v1/ui/session", headers=_headers())
    assert viewer.status_code == 403 and viewer.json()["code"] == "FORBIDDEN"
    assert no_origin.status_code == 403
    assert evil.status_code == 403
    assert ok.status_code == 200
    assert ps256.status_code == 200 and ps256.json()["userId"] == "u1"
    assert ok.json()["enabled"] is True and ok.json()["userId"] == "u1"
    assert ok.json()["roles"] == ["datalens.admin"]
    assert expired.status_code == 401
    assert hs256.status_code == 401
    assert empty_cookie.status_code == 401
    assert no_cookie.status_code == 401


def test_chat_binds_thread_and_followup(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    with _client(ScriptedLLM([text("первый"), text("второй")])) as client:
        first = client.post("/v1/ui/chat", json={"message": "вопрос 1"}, headers=headers)
        thread = client.get("/v1/ui/thread", headers=headers)
        second = client.post("/v1/ui/chat", json={"message": "вопрос 2"}, headers=headers)
        reset = client.post("/v1/ui/new", headers=headers)
        after = client.get("/v1/ui/thread", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["reply"] == "первый"
    assert thread.status_code == 200
    body = thread.json()
    assert body["conversationId"] == first.json()["conversationId"]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "вопрос 1"
    assert body["messages"][1]["content"] == "первый"
    assert second.status_code == 200, second.text
    assert second.json()["conversationId"] == first.json()["conversationId"]
    assert second.json()["reply"] == "второй"
    assert reset.status_code == 200 and reset.json() == {"ok": True}
    assert after.status_code == 200
    assert after.json()["conversationId"] is None and after.json()["messages"] == []


def test_chat_passes_open_page(monkeypatch):
    _enable(monkeypatch)
    llm = ScriptedLLM([text("смотри вкладку")])
    with _client(llm) as client:
        ok = client.post(
            "/v1/ui/chat",
            json={"message": "что не оптимально", "context": {"dashboardId": "demo-dashboard", "tabId": "sales"}},
            headers=_headers(_token()),
        )
        bad = client.post(
            "/v1/ui/chat",
            json={"message": "ещё", "context": {"dashboardId": "x" * 80}},
            headers=_headers(_token()),
        )
    assert ok.status_code == 200, ok.text
    system = llm.calls[0]["messages"][0]["content"]
    assert "demo-dashboard" in system and "вкладка sales" in system
    assert llm.calls[0]["messages"][-1]["content"] == "что не оптимально"
    assert bad.status_code == 400 and bad.json()["code"] == "INVALID_ARGUMENT"


def test_chat_still_requires_service_token(monkeypatch):
    _enable(monkeypatch)
    with _client(ScriptedLLM([text("ok")])) as client:
        missing = client.post("/v1/chat", json={"message": "hi"})
        ok = client.post("/v1/chat", json={"message": "hi"}, headers={"Authorization": "Bearer test-neuro-token"})
    assert missing.status_code == 401
    assert ok.status_code == 200, ok.text
    assert ok.json()["reply"] == "ok"


def test_cors_allows_listed_origin(monkeypatch):
    _enable(monkeypatch)
    with _client() as client:
        response = client.get("/v1/ui/session", headers=_headers(_token()))
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
