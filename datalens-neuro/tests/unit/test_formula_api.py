import asyncio
import json
import time
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.clients.datalens_api import DatalensApiError
from app.config import get_settings
from app.llm.base import LLMError
from app.main import create_app
from tests.fakes import ScriptedLLM, text

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = PRIVATE.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
ORIGIN = "http://127.0.0.1:8080"
OPEN_CHART = "Откройте чарт: формулы собираются по полям его датасета"


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


_CHART = {
    "workbookId": "wb",
    "type": "graph_wizard_node",
    "data": {"shared": {"datasetsIds": ["ds1"]}},
}
_DATASET = {
    "id": "ds1",
    "workbookId": "wb",
    "mtime": "t1",
    "dataset": {"result_schema": [
        {"guid": "g1", "title": "Выручка", "type": "MEASURE", "data_type": "float", "aggregation": "sum"},
    ]},
}
_WIZARD = {"message": "сумма", "context": {"chartId": "c1", "chartKind": "wizard"}}


class _ChartApi:
    def __init__(self, errors=None):
        self.errors = errors or {}

    async def rpc(self, method, args):
        if method in self.errors:
            raise self.errors[method]
        if method == "getWizardChart":
            return _CHART
        if method == "getDataset":
            return _DATASET
        return {"valid": True}


def _client(llm=None, api=None) -> TestClient:
    llm = llm or ScriptedLLM([])
    kwargs = {"llm_factory": lambda _settings: llm}
    if api is not None:
        kwargs["api_factory"] = lambda _settings: api
    return TestClient(create_app(**kwargs))


@asynccontextmanager
async def _lifespan(app):
    shutdown = asyncio.Event()
    ready = asyncio.Event()
    calls = 0

    async def receive():
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"type": "lifespan.startup"}
        await shutdown.wait()
        return {"type": "lifespan.shutdown"}

    async def send(message):
        if message["type"] == "lifespan.startup.complete":
            ready.set()
        elif message["type"] == "lifespan.startup.failed":
            ready.set()

    task = asyncio.create_task(app({"type": "lifespan"}, receive, send))
    await ready.wait()
    try:
        yield
    finally:
        shutdown.set()
        await task


def test_formula_hidden_when_ui_disabled():
    with _client() as client:
        response = client.post("/v1/ui/formula", json={"message": "q"}, headers=_headers(_token()))
    assert response.status_code == 404


def test_formula_disabled_neuro(monkeypatch):
    _enable(monkeypatch, NEURO_ENABLED="false")
    with _client() as client:
        thread = client.get("/v1/ui/formula/thread")
        chat = client.post("/v1/ui/formula", json={"message": "q"})
    assert thread.status_code == 200 and thread.json() == {"enabled": False}
    assert chat.status_code == 503 and chat.json()["code"] == "NEURO_DISABLED"


def test_formula_requires_cookie(monkeypatch):
    _enable(monkeypatch)
    with _client() as client:
        response = client.post("/v1/ui/formula", json={"message": "q"}, headers=_headers())
    assert response.status_code == 401


def test_sheet_chart_kind_is_rejected_and_not_stored(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    with _client() as client:
        bad = client.post(
            "/v1/ui/formula",
            json={"message": "сумма", "context": {"chartId": "c1", "chartKind": "sheet"}},
            headers=headers,
        )
        thread = client.get("/v1/ui/formula/thread", headers=headers)
    assert bad.status_code == 400 and bad.json()["code"] == "INVALID_ARGUMENT"
    assert thread.status_code == 200
    assert thread.json()["messages"] == []


def test_missing_chart_replies_with_open_chart_and_keeps_it(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    with _client(ScriptedLLM([])) as client:
        first = client.post(
            "/v1/ui/formula",
            json={"message": "сумма продаж", "context": {"tabId": "ignored"}},
            headers=headers,
        )
        thread = client.get("/v1/ui/formula/thread", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["reply"] == OPEN_CHART
    assert first.json()["steps"] == []
    assert first.json()["sources"] == []
    assert thread.status_code == 200
    assert thread.json()["messages"][1]["role"] == "assistant"
    assert thread.json()["messages"][1]["content"] == OPEN_CHART


def test_formula_new_clears_only_formula_thread(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    with _client(ScriptedLLM([text("ок")])) as client:
        dash = client.post("/v1/ui/chat", json={"message": "вопрос"}, headers=headers)
        formula = client.post("/v1/ui/formula", json={"message": "формула"}, headers=headers)
        reset = client.post("/v1/ui/formula/new", headers=headers)
        formula_thread = client.get("/v1/ui/formula/thread", headers=headers)
        dash_thread = client.get("/v1/ui/thread", headers=headers)
    assert dash.status_code == 200, dash.text
    assert formula.status_code == 200, formula.text
    assert reset.status_code == 200 and reset.json() == {"ok": True}
    assert formula_thread.json()["conversationId"] is None
    assert formula_thread.json()["messages"] == []
    assert [item["content"] for item in dash_thread.json()["messages"]] == ["вопрос", "ок"]


def test_formula_turn_shares_rate_limit_with_chat(monkeypatch):
    _enable(monkeypatch, NEURO_RATE_LIMIT_PER_MIN="1")
    headers = _headers(_token())
    with _client(ScriptedLLM([text("ок")])) as client:
        formula = client.post("/v1/ui/formula", json={"message": "формула"}, headers=headers)
        chat = client.post("/v1/ui/chat", json={"message": "вопрос"}, headers=headers)
    assert formula.status_code == 200, formula.text
    assert chat.status_code == 429 and chat.json()["code"] == "RESOURCE_EXHAUSTED"


def _assert_thread_empty(thread):
    assert thread.status_code == 200
    assert thread.json()["messages"] == []


def test_llm_error_is_502_and_thread_stays_empty(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    with _client(ScriptedLLM([LLMError("timeout")]), _ChartApi()) as client:
        bad = client.post("/v1/ui/formula", json=_WIZARD, headers=headers)
        thread = client.get("/v1/ui/formula/thread", headers=headers)
    assert bad.status_code == 502 and bad.json()["code"] == "LLM_UNAVAILABLE"
    _assert_thread_empty(thread)


def test_datalens_504_is_deadline_and_thread_stays_empty(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    secret = "upstream SUM([Выручка])"
    api = _ChartApi(errors={"getWizardChart": DatalensApiError(504, "DEADLINE_EXCEEDED", secret)})
    with _client(api=api) as client:
        bad = client.post("/v1/ui/formula", json=_WIZARD, headers=headers)
        thread = client.get("/v1/ui/formula/thread", headers=headers)
    body = bad.json()
    assert bad.status_code == 504 and body["code"] == "DEADLINE_EXCEEDED"
    assert set(body["details"]) == {"deadlineSec"}
    assert secret not in bad.text
    _assert_thread_empty(thread)


def test_escaped_datalens_401_is_502_and_thread_stays_empty(monkeypatch):
    _enable(monkeypatch)
    headers = _headers(_token())
    secret = "upstream token SUM([Секрет])"
    llm = ScriptedLLM([DatalensApiError(401, "UNAUTHENTICATED", secret)])
    with _client(llm, _ChartApi()) as client:
        bad = client.post("/v1/ui/formula", json=_WIZARD, headers=headers)
        thread = client.get("/v1/ui/formula/thread", headers=headers)
    body = bad.json()
    assert bad.status_code == 502 and body["code"] == "UNAVAILABLE"
    assert body["details"] == {}
    assert secret not in bad.text
    _assert_thread_empty(thread)


async def test_overlapping_formula_posts_are_busy(monkeypatch):
    _enable(monkeypatch)
    started = asyncio.Event()
    held = asyncio.Lock()
    await held.acquire()

    async def slow(_messages, _tools):
        started.set()
        async with held:
            return text('{"explanation": "готово", "formula": null}')

    headers = _headers(_token())
    app = create_app(
        llm_factory=lambda _settings: ScriptedLLM([slow]),
        api_factory=lambda _settings: _ChartApi(),
    )
    transport = httpx.ASGITransport(app=app)
    async with _lifespan(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            seed = await client.post("/v1/ui/formula", json={"message": "seed"}, headers=headers)
            assert seed.status_code == 200, seed.text
            first = asyncio.create_task(
                client.post("/v1/ui/formula", json={**_WIZARD, "message": "первый"}, headers=headers)
            )
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                second = await client.post(
                    "/v1/ui/formula", json={**_WIZARD, "message": "второй"}, headers=headers
                )
            finally:
                if held.locked():
                    held.release()
            first_response = await first
            thread = await client.get("/v1/ui/formula/thread", headers=headers)
    assert second.status_code == 409 and second.json()["code"] == "CONVERSATION_BUSY"
    assert first_response.status_code == 200
    contents = [item["content"] for item in thread.json()["messages"]]
    assert "второй" not in contents
