import json

import httpx
import pytest
import respx

from app.config import get_settings
from app.llm.base import LLMError
from app.llm.factory import build_llm
from app.llm.openai_compatible import OpenAICompatibleProvider, parse_tool_calls

URL = "http://llm.example/v1/chat/completions"


def _provider(max_retries: int = 2) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "http://llm.example/v1/",
        "secret-key",
        "test-model",
        timeout_sec=5,
        max_retries=max_retries,
        retry_delays=(0.0,),
    )


def _completion(message: dict, usage: dict | None = None) -> dict:
    return {"choices": [{"message": message}], "usage": usage or {"prompt_tokens": 11, "completion_tokens": 7}}


@respx.mock
async def test_text_answer_and_usage():
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json=_completion({"role": "assistant", "content": "Привет"}))
    )
    response = await _provider().chat([{"role": "user", "content": "hi"}])
    assert response.content == "Привет" and response.tool_calls == []
    assert (response.prompt_tokens, response.completion_tokens) == (11, 7)
    sent = json.loads(route.calls[0].request.content)
    assert sent["model"] == "test-model" and "tools" not in sent
    assert route.calls[0].request.headers["authorization"] == "Bearer secret-key"


@respx.mock
async def test_tool_calls_are_parsed_and_tools_sent():
    route = respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json=_completion(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "get_dataset", "arguments": "{\"datasetId\": \"ds1\"}"}},
                        {"id": "call_2", "type": "function", "function": {"name": "query_dataset", "arguments": "{broken"}},
                    ],
                }
            ),
        )
    )
    tools = [{"type": "function", "function": {"name": "get_dataset", "parameters": {"type": "object"}}}]
    response = await _provider().chat([{"role": "user", "content": "q"}], tools)
    first, second = response.tool_calls
    assert (first.id, first.name, first.arguments) == ("call_1", "get_dataset", {"datasetId": "ds1"})
    assert second.arguments is None and second.raw_arguments == "{broken"
    sent = json.loads(route.calls[0].request.content)
    assert sent["tools"] == tools and sent["tool_choice"] == "auto"


@respx.mock
async def test_retries_on_429_then_succeeds():
    route = respx.post(URL).mock(
        side_effect=[httpx.Response(429, json={}), httpx.Response(200, json=_completion({"content": "ok"}))]
    )
    assert (await _provider().chat([])).content == "ok"
    assert route.call_count == 2


@respx.mock
async def test_retries_on_timeout_then_gives_up():
    route = respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(LLMError, match="timeout"):
        await _provider(max_retries=2).chat([])
    assert route.call_count == 3


@respx.mock
async def test_client_error_is_not_retried_and_hides_key():
    route = respx.post(URL).mock(
        return_value=httpx.Response(401, json={"error": {"message": "Invalid API key"}})
    )
    with pytest.raises(LLMError) as exc:
        await _provider().chat([])
    assert route.call_count == 1
    assert exc.value.category == "http_401" and str(exc.value) == "http_401"
    assert "Invalid API key" not in str(exc.value) and "secret-key" not in str(exc.value)


@respx.mock
async def test_error_categories():
    respx.post(URL).mock(side_effect=httpx.ConnectError("refused: secret-host"))
    with pytest.raises(LLMError) as transport:
        await _provider(max_retries=0).chat([])
    respx.post(URL).mock(return_value=httpx.Response(503, json={"error": {"message": "overloaded"}}))
    with pytest.raises(LLMError) as http:
        await _provider(max_retries=1).chat([])
    respx.post(URL).mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(LLMError) as invalid:
        await _provider().chat([])
    assert transport.value.category == "transport" and "secret-host" not in str(transport.value)
    assert http.value.category == "http_503" and "overloaded" not in str(http.value)
    assert invalid.value.category == "invalid_response"


@respx.mock
async def test_response_without_choices_is_error():
    respx.post(URL).mock(return_value=httpx.Response(200, json={"choices": []}))
    with pytest.raises(LLMError):
        await _provider().chat([])


@respx.mock
async def test_tool_choice_none_is_sent_with_tools():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=_completion({"content": "ok"})))
    tools = [{"type": "function", "function": {"name": "get_dataset", "parameters": {"type": "object"}}}]
    await _provider().chat([], tools, tool_choice="none")
    sent = json.loads(route.calls[0].request.content)
    assert sent["tools"] == tools and sent["tool_choice"] == "none"


def test_empty_tool_call_id_is_generated():
    message = {
        "tool_calls": [
            {"id": "", "function": {"name": "a", "arguments": "{}"}},
            {"function": {"name": "b", "arguments": "{}"}},
            {"id": "real", "function": {"name": "c", "arguments": "{}"}},
        ]
    }
    assert [c.id for c in parse_tool_calls(message)] == ["call_0", "call_1", "real"]


@respx.mock
async def test_shared_client_is_reused_and_closed():
    respx.post(URL).mock(return_value=httpx.Response(200, json=_completion({"content": "ok"})))
    provider = _provider()
    client = provider._client
    await provider.chat([])
    await provider.chat([])
    assert provider._client is client and not client.is_closed
    await provider.aclose()
    assert client.is_closed


def test_factory(monkeypatch):
    assert isinstance(build_llm(get_settings()), OpenAICompatibleProvider)
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    assert build_llm(get_settings()) is None
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    assert build_llm(get_settings()) is None
