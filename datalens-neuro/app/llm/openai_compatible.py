import asyncio
import json
from collections.abc import Sequence
from typing import Any

import httpx

from app.llm.base import LLMError, LLMResponse, ToolCall

_RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}


def parse_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, raw in enumerate(message.get("tool_calls") or []):
        if not isinstance(raw, dict):
            continue
        function = raw.get("function") or {}
        raw_args = function.get("arguments")
        if isinstance(raw_args, dict):
            arguments: dict[str, Any] | None = raw_args
            text = json.dumps(raw_args, ensure_ascii=False)
        else:
            text = raw_args or "{}"
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            arguments = parsed if isinstance(parsed, dict) else None
        calls.append(
            ToolCall(
                id=str(raw.get("id") or f"call_{index}"),
                name=str(function.get("name") or ""),
                arguments=arguments,
                raw_arguments=text,
            )
        )
    return calls


def _usage(payload: dict[str, Any], key: str) -> int:
    usage = payload.get("usage")
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) else 0


def _to_response(payload: Any) -> LLMResponse:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not choices or not isinstance(choices[0], dict):
        raise LLMError("invalid_response")
    message = choices[0].get("message") or {}
    content = message.get("content")
    return LLMResponse(
        content=content if isinstance(content, str) else None,
        tool_calls=parse_tool_calls(message),
        prompt_tokens=_usage(payload, "prompt_tokens"),
        completion_tokens=_usage(payload, "completion_tokens"),
    )


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout_sec: float,
        max_retries: int,
        retry_delays: Sequence[float] = (2.0, 5.0),
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._max_retries = max(max_retries, 0)
        self._retry_delays = tuple(retry_delays) or (0.0,)
        self._client = httpx.AsyncClient(timeout=timeout_sec)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        body: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice
        last_error = "no attempts"
        for attempt in range(self._max_retries + 1):
            if attempt:
                await asyncio.sleep(self._retry_delays[min(attempt - 1, len(self._retry_delays) - 1)])
            try:
                response = await self._client.post(
                    self._url, json=body, headers={"Authorization": f"Bearer {self._api_key}"}
                )
            except httpx.TimeoutException:
                last_error = "timeout"
                continue
            except httpx.TransportError:
                last_error = "transport"
                continue
            if response.status_code in _RETRY_STATUSES:
                last_error = f"http_{response.status_code}"
                continue
            if response.status_code >= 400:
                raise LLMError(f"http_{response.status_code}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise LLMError("invalid_response") from exc
            return _to_response(payload)
        raise LLMError(last_error)
