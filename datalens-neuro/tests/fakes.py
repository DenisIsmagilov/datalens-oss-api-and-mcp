import copy
import json
from typing import Any

from app.llm.base import LLMResponse, ToolCall


class ScriptedLLM:
    """Отдаёт заранее заданные ответы по порядку; элемент — LLMResponse, исключение или async-функция (messages, tools)."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, messages, tools=None, *, tool_choice="auto") -> LLMResponse:
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools, "tool_choice": tool_choice})
        if not self.script:
            raise AssertionError("ScriptedLLM: no more scripted responses")
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            return await item(messages, tools)
        return item


def text(content: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> LLMResponse:
    return LLMResponse(content=content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


def call(name: str, args: dict | str, call_id: str | None = None) -> LLMResponse:
    if isinstance(args, dict):
        raw, parsed = json.dumps(args, ensure_ascii=False), args
    else:
        raw = args
        try:
            loaded = json.loads(args)
        except json.JSONDecodeError:
            loaded = None
        parsed = loaded if isinstance(loaded, dict) else None
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id=call_id or f"call_{name}", name=name, arguments=parsed, raw_arguments=raw)],
        prompt_tokens=10,
        completion_tokens=5,
    )
