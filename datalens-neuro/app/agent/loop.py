import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.prompt import FINAL_ANSWER_INSTRUCTION
from app.llm.base import LLMError, LLMProvider, LLMResponse, ToolCall
from app.models import Step, TurnResult
from app.request_context import current_request_id
from app.tools.base import ToolContext, ToolError, ToolRegistry, run_tool

_TRUNCATION_MARK = "\n…[truncated: the result is longer than {limit} characters; narrow the request]"
_EMPTY_REPLY = "(пустой ответ модели)"
_llm_logger = logging.getLogger("datalens_neuro.llm")
_tools_logger = logging.getLogger("datalens_neuro.tools")
HINTS = {
    "DEADLINE_EXCEEDED": "The request is too heavy. Use query_dataset with filters and fewer fields instead.",
    "OUT_OF_SCOPE": "Only entities from the pack workbooks are available. Use list_workbook_entries to find them.",
}


class TurnDeadlineError(Exception):
    pass


@dataclass
class LoopConfig:
    max_rounds: int
    deadline_sec: float
    tool_result_max_chars: int
    llm_timeout_sec: float


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    mark = _TRUNCATION_MARK.format(limit=limit)
    return text[: max(limit - len(mark), 0)] + mark


def unavailable_reply(steps: list[Step]) -> str:
    lines = ["Модель недоступна, ответ не сформирован."]
    if steps:
        lines.append("Выполненные шаги:")
        lines.extend(f"- {step.tool}: {step.status}" for step in steps)
    return "\n".join(lines)


def _assistant_message(response: LLMResponse) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.raw_arguments
                    or json.dumps(tool_call.arguments or {}, ensure_ascii=False),
                },
            }
            for tool_call in response.tool_calls
        ],
    }


def _error_payload(code: str, message: str, details: dict | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    if code in HINTS:
        error["hint"] = HINTS[code]
    return {"error": error}


async def _execute(
    tool_call: ToolCall, registry: ToolRegistry, ctx: ToolContext, timeout: float
) -> tuple[Step, str]:
    started = time.monotonic()
    tool = registry.get(tool_call.name)
    args = tool_call.arguments if tool_call.arguments is not None else {"_raw": tool_call.raw_arguments[:500]}
    row_count = None
    if tool is None:
        status = "UNKNOWN_TOOL"
        payload = _error_payload(status, f"Unknown tool {tool_call.name!r}", {"availableTools": registry.names})
    elif tool_call.arguments is None:
        status = "INVALID_ARGUMENT"
        payload = _error_payload(status, "Tool arguments are not valid JSON")
    elif timeout <= 0:
        status = "DEADLINE_EXCEEDED"
        payload = _error_payload(status, "The turn deadline was reached before this call")
    else:
        try:
            payload = await asyncio.wait_for(run_tool(tool, tool_call.arguments, ctx), timeout=timeout)
            status = "OK"
            if isinstance(payload.get("rowCount"), int):
                row_count = payload["rowCount"]
        except ToolError as exc:
            status = exc.code
            payload = _error_payload(exc.code, exc.message, exc.details)
        except TimeoutError:
            status = "DEADLINE_EXCEEDED"
            payload = _error_payload(status, "The turn deadline was reached during this call")
        except Exception:
            _tools_logger.exception("tool failed trace_id=%s tool=%s", current_request_id(), tool_call.name)
            status = "INTERNAL"
            payload = _error_payload(status, "Tool failed")
    step = Step(
        tool=tool_call.name,
        args=args,
        status=status,
        duration_ms=int((time.monotonic() - started) * 1000),
        row_count=row_count,
    )
    return step, json.dumps(payload, ensure_ascii=False, default=str)


def _add_source(result: TurnResult, registry: ToolRegistry, tool_call: ToolCall, step: Step) -> None:
    tool = registry.get(tool_call.name)
    if step.status != "OK" or tool is None or not tool.source_type or not tool_call.arguments:
        return
    source_id = tool_call.arguments.get(tool.source_arg or "")
    if not source_id:
        return
    source = {"type": tool.source_type, "id": str(source_id)}
    if source not in result.sources:
        result.sources.append(source)


async def run_turn(
    *,
    llm: LLMProvider,
    registry: ToolRegistry,
    ctx: ToolContext,
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    config: LoopConfig,
    clock: Callable[[], float] = time.monotonic,
) -> TurnResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]
    tools = registry.schemas()
    started = clock()
    result = TurnResult(reply="", stop_reason="answer")

    def remaining() -> float:
        return config.deadline_sec - (clock() - started)

    stop = "max_rounds"
    while result.rounds < config.max_rounds:
        left = remaining()
        if left <= 0:
            stop = "deadline"
            break
        try:
            response = await asyncio.wait_for(llm.chat(messages, tools), timeout=left)
        except TimeoutError:
            if result.rounds == 0:
                raise TurnDeadlineError() from None
            stop = "deadline"
            break
        except LLMError as exc:
            if result.rounds == 0:
                raise
            _llm_logger.warning("llm unavailable trace_id=%s reason=%s", current_request_id(), exc.category)
            stop = "llm_unavailable"
            break
        result.rounds += 1
        result.prompt_tokens += response.prompt_tokens
        result.completion_tokens += response.completion_tokens
        if not response.tool_calls:
            result.reply = (response.content or "").strip() or _EMPTY_REPLY
            result.stop_reason = "answer"
            return result
        messages.append(_assistant_message(response))
        for tool_call in response.tool_calls:
            step, content = await _execute(tool_call, registry, ctx, remaining())
            result.steps.append(step)
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": truncate(content, config.tool_result_max_chars)}
            )
            _add_source(result, registry, tool_call, step)

    result.stop_reason = stop
    if stop == "llm_unavailable":
        result.reply = unavailable_reply(result.steps)
        return result
    messages.append({"role": "user", "content": FINAL_ANSWER_INSTRUCTION})
    try:
        response = await asyncio.wait_for(
            llm.chat(messages, tools, tool_choice="none"), timeout=config.llm_timeout_sec
        )
    except (TimeoutError, LLMError) as exc:
        if isinstance(exc, LLMError):
            _llm_logger.warning("llm unavailable trace_id=%s reason=%s", current_request_id(), exc.category)
        result.stop_reason = "llm_unavailable"
        result.reply = unavailable_reply(result.steps)
        return result
    result.prompt_tokens += response.prompt_tokens
    result.completion_tokens += response.completion_tokens
    result.reply = (response.content or "").strip() or unavailable_reply(result.steps)
    return result
