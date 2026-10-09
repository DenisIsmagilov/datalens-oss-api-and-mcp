import logging
import re

import httpx
import respx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.llm.base import LLMError
from app.main import create_app
from tests.fakes import ScriptedLLM, call, text

API = "http://datalens-api.example:8393"
AUTH = {"Authorization": "Bearer test-neuro-token"}


def _client(llm) -> TestClient:
    return TestClient(create_app(llm_factory=lambda _settings: llm))


def test_chat_requires_token():
    with _client(ScriptedLLM([])) as client:
        missing = client.post("/v1/chat", json={"message": "hi"})
        wrong = client.post("/v1/chat", json={"message": "hi"}, headers={"Authorization": "Bearer nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401 and wrong.json()["code"] == "UNAUTHENTICATED"


def test_chat_disabled(monkeypatch):
    monkeypatch.setenv("NEURO_ENABLED", "false")
    get_settings.cache_clear()
    with _client(ScriptedLLM([])) as client:
        response = client.post("/v1/chat", json={"message": "hi"}, headers=AUTH)
        health = client.get("/health")
    assert response.status_code == 503 and response.json()["code"] == "NEURO_DISABLED"
    assert health.status_code == 200 and health.json()["enabled"] is False


def test_simple_answer_and_log_line(caplog):
    llm = ScriptedLLM([text("Ответ")])
    with caplog.at_level(logging.INFO, logger="datalens_neuro.turn"), _client(llm) as client:
        response = client.post(
            "/v1/chat", json={"message": "Секретный вопрос"}, headers={**AUTH, "x-request-id": "trace-chat"}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert re.fullmatch(r"c_[0-9a-f]{20}", body["conversationId"])
    assert (body["reply"], body["stopReason"], body["steps"], body["sources"]) == ("Ответ", "answer", [], [])
    assert body["usage"] == {"rounds": 1, "promptTokens": 10, "completionTokens": 5}
    assert response.headers["x-request-id"] == "trace-chat"
    assert "trace_id=trace-chat" in caplog.text and "status=OK" in caplog.text
    assert "Секретный" not in caplog.text and "Ответ" not in caplog.text
    assert "Сейчас:" in llm.calls[0]["messages"][0]["content"]


@respx.mock
def test_tool_flow_history_and_detail():
    route = respx.post(f"{API}/rpc/queryDataset").mock(
        return_value=httpx.Response(200, json={"columns": [{"title": "n", "dataType": "integer"}], "rows": [[5]], "rowCount": 1, "truncated": False})
    )
    llm = ScriptedLLM([call("query_dataset", {"datasetId": "ds1", "fields": ["n"]}), text("Пять"), text("Повторю: пять")])
    with _client(llm) as client:
        first = client.post("/v1/chat", json={"message": "Сколько?"}, headers={**AUTH, "x-request-id": "trace-tool"}).json()
        second = client.post("/v1/chat", json={"message": "Ещё раз?", "conversationId": first["conversationId"]}, headers=AUTH).json()
        detail = client.get(f"/v1/conversations/{first['conversationId']}", headers=AUTH).json()
    step = first["steps"][0]
    assert (step["tool"], step["status"], step["rowCount"]) == ("query_dataset", "OK", 1)
    assert first["sources"] == [{"type": "dataset", "id": "ds1"}]
    assert route.calls[0].request.headers["x-request-id"] == "trace-tool"
    assert second["reply"] == "Повторю: пять"
    third = llm.calls[2]["messages"]
    assert [m["role"] for m in third] == ["system", "user", "assistant", "user"]
    assert (third[1]["content"], third[2]["content"], third[3]["content"]) == ("Сколько?", "Пять", "Ещё раз?")
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["messages"][1]["steps"][0]["tool"] == "query_dataset"


def test_conversation_errors():
    with _client(ScriptedLLM([text("a")])) as client:
        missing = client.post("/v1/chat", json={"message": "q", "conversationId": "c_" + "0" * 20}, headers=AUTH)
        unknown_pack = client.post("/v1/chat", json={"message": "q", "pack": "nope"}, headers=AUTH)
        created = client.post("/v1/chat", json={"message": "q"}, headers=AUTH).json()
        changed = client.post(
            "/v1/chat", json={"message": "q", "conversationId": created["conversationId"], "pack": "demo"}, headers=AUTH
        )
        no_detail = client.get("/v1/conversations/c_" + "0" * 20, headers=AUTH)
        bad_body = client.post("/v1/chat", json={"message": ""}, headers=AUTH)
    assert missing.status_code == 404
    assert unknown_pack.status_code == 404 and unknown_pack.json()["details"]["pack"] == "nope"
    assert changed.status_code == 400 and changed.json()["details"]["pack"] == "default"
    assert no_detail.status_code == 404
    assert bad_body.status_code == 400 and bad_body.json()["code"] == "INVALID_ARGUMENT"


def test_rate_limit_per_channel_user(monkeypatch):
    monkeypatch.setenv("NEURO_RATE_LIMIT_PER_MIN", "1")
    get_settings.cache_clear()
    with _client(ScriptedLLM([text("a"), text("b")])) as client:
        ok = client.post("/v1/chat", json={"message": "q", "user": {"externalId": "tg:1"}}, headers=AUTH)
        limited = client.post("/v1/chat", json={"message": "q", "user": {"externalId": "tg:1"}}, headers=AUTH)
        other = client.post("/v1/chat", json={"message": "q", "user": {"externalId": "tg:2"}}, headers=AUTH)
    assert ok.status_code == 200 and other.status_code == 200
    assert limited.status_code == 429 and limited.json()["code"] == "RESOURCE_EXHAUSTED"


def test_llm_not_configured():
    with TestClient(create_app(llm_factory=lambda _settings: None)) as client:
        response = client.post("/v1/chat", json={"message": "q"}, headers=AUTH)
        health = client.get("/health").json()
    assert response.status_code == 502 and response.json()["code"] == "LLM_UNAVAILABLE"
    assert health["llmConfigured"] is False


def test_llm_error_is_502_with_category_only(caplog):
    with caplog.at_level(logging.WARNING, logger="datalens_neuro.llm"), _client(ScriptedLLM([LLMError("http_401")])) as client:
        response = client.post("/v1/chat", json={"message": "q"}, headers={**AUTH, "x-request-id": "trace-502"})
    body = response.json()
    assert response.status_code == 502 and body["code"] == "LLM_UNAVAILABLE"
    assert body["details"] == {"reason": "http_401"}
    assert "llm unavailable trace_id=trace-502 reason=http_401" in caplog.text


def test_failed_turns_leave_no_orphan_questions():
    llm = ScriptedLLM([text("Ответ"), LLMError("timeout"), LLMError("timeout")])
    with _client(llm) as client:
        first = client.post("/v1/chat", json={"message": "q1"}, headers=AUTH).json()
        failed = client.post("/v1/chat", json={"message": "q2", "conversationId": first["conversationId"]}, headers=AUTH)
        detail = client.get(f"/v1/conversations/{first['conversationId']}", headers=AUTH).json()
        again = client.post("/v1/chat", json={"message": "q3"}, headers=AUTH)
    assert failed.status_code == 502 and again.status_code == 502
    assert [m["content"] for m in detail["messages"]] == ["q1", "Ответ"]


def test_status_loader_and_health(monkeypatch):
    with _client(ScriptedLLM([])) as client:
        status = client.get("/v1/status", headers=AUTH).json()
        unauthorized = client.get("/v1/status")
        loader = client.get("/ui/loader.js")
        health = client.get("/health").json()
    assert (status["enabled"], status["uiEnabled"], status["defaultPack"], status["model"]) == (True, False, "default", "test-model")
    assert {p["name"] for p in status["packs"]} == {"default", "demo"} and status["packErrors"] == {}
    assert unauthorized.status_code == 401
    assert loader.status_code == 200
    assert loader.headers["content-type"].startswith("application/javascript")
    assert loader.headers["cache-control"] == "no-store"
    assert "ui disabled" in loader.text
    assert health == {"status": "ok", "enabled": True, "db": "ok", "packs": 2, "llmConfigured": True, "defaultPack": "ok"}
    monkeypatch.setenv("NEURO_UI_ENABLED", "true")
    monkeypatch.setenv("NEURO_UI_TITLE", "Фотосклад AI")
    get_settings.cache_clear()
    with _client(ScriptedLLM([])) as client:
        script = client.get("/ui/loader.js").text
    assert "datalens-neuro-root" in script
    assert '"Фотосклад AI"' in script
    assert "__NEURO_UI_TITLE_JSON__" not in script
