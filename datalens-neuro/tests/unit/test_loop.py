import asyncio
import json
import logging

import pytest
from pydantic import BaseModel, ConfigDict

from app.agent.loop import LoopConfig, TurnDeadlineError, run_turn, truncate
from app.agent.prompt import FINAL_ANSWER_INSTRUCTION
from app.llm.base import LLMError
from app.packs import Pack
from app.tools.base import Tool, ToolContext, ToolError, ToolRegistry
from app.tools.scope_cache import ScopeCache
from tests.fakes import ScriptedLLM, call, text


class EchoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


async def _echo(args, _ctx):
    return {"rowCount": 2, "echo": args.value}


async def _boom(_args, _ctx):
    raise ToolError("DEADLINE_EXCEEDED", "chart is too heavy")


async def _crash(_args, _ctx):
    raise KeyError("x")


async def _big(_args, _ctx):
    return {"blob": "x" * 5000}


REGISTRY = ToolRegistry(
    [
        Tool("echo", "Echo the value back; used only in tests of the agent loop.", EchoArgs, _echo, source_type="dataset", source_arg="value"),
        Tool("boom", "Always fails with DEADLINE_EXCEEDED; used only in loop tests.", EchoArgs, _boom),
        Tool("big", "Returns a very large payload; used only in truncation tests.", EchoArgs, _big),
    ]
)
CTX = ToolContext(api=None, pack=Pack(name="default", title="", workbook_ids=[]), scope=ScopeCache())
CONFIG = LoopConfig(max_rounds=5, deadline_sec=60, tool_result_max_chars=1000, llm_timeout_sec=5)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


CRASH_REGISTRY = ToolRegistry(
    [Tool("crash", "Raises an unexpected KeyError; used only in loop tests.", EchoArgs, _crash)]
)


async def _turn(llm, *, config=CONFIG, history=None, clock=None, registry=REGISTRY):
    extra = {"clock": clock} if clock else {}
    return await run_turn(
        llm=llm,
        registry=registry,
        ctx=CTX,
        system_prompt="SYS",
        history=history or [],
        user_message="вопрос",
        config=config,
        **extra,
    )


async def test_immediate_answer_with_history():
    llm = ScriptedLLM([text("Ответ")])
    history = [{"role": "user", "content": "раньше"}, {"role": "assistant", "content": "было"}]
    result = await _turn(llm, history=history)
    assert (result.reply, result.stop_reason, result.rounds) == ("Ответ", "answer", 1)
    assert (result.prompt_tokens, result.completion_tokens) == (10, 5)
    assert llm.calls[0]["messages"] == [{"role": "system", "content": "SYS"}, *history, {"role": "user", "content": "вопрос"}]
    assert [t["function"]["name"] for t in llm.calls[0]["tools"]] == ["echo", "boom", "big"]


async def test_tool_then_answer():
    llm = ScriptedLLM([call("echo", {"value": "ds1"}), text("Итог")])
    result = await _turn(llm)
    assert result.reply == "Итог" and result.rounds == 2
    step = result.steps[0]
    assert (step.tool, step.status, step.row_count, step.args) == ("echo", "OK", 2, {"value": "ds1"})
    assert result.sources == [{"type": "dataset", "id": "ds1"}]
    second = llm.calls[1]["messages"]
    assert second[-2]["role"] == "assistant"
    assert second[-2]["tool_calls"][0]["function"] == {"name": "echo", "arguments": json.dumps({"value": "ds1"})}
    assert second[-1] == {"role": "tool", "tool_call_id": "call_echo", "content": json.dumps({"rowCount": 2, "echo": "ds1"}, ensure_ascii=False)}


@pytest.mark.parametrize(
    ("response", "status"),
    [
        (call("echo", {"wrong": 1}), "INVALID_ARGUMENT"),
        (call("missing_tool", {}), "UNKNOWN_TOOL"),
        (call("echo", "{broken"), "INVALID_ARGUMENT"),
    ],
)
async def test_tool_errors_go_back_to_model(response, status):
    llm = ScriptedLLM([response, text("Исправился")])
    result = await _turn(llm)
    assert result.steps[0].status == status and result.sources == []
    assert status in llm.calls[1]["messages"][-1]["content"]
    assert result.reply == "Исправился"


async def test_deadline_error_from_tool_has_hint():
    llm = ScriptedLLM([call("boom", {"value": "c1"}), text("Через query_dataset")])
    result = await _turn(llm)
    payload = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert payload["error"]["code"] == "DEADLINE_EXCEEDED"
    assert "query_dataset" in payload["error"]["hint"]
    assert result.steps[0].status == "DEADLINE_EXCEEDED"


async def test_max_rounds_ends_with_answer_and_tool_choice_none():
    llm = ScriptedLLM([call("echo", {"value": "a"}), call("echo", {"value": "b"}), text("Что успел")])
    result = await _turn(llm, config=LoopConfig(max_rounds=2, deadline_sec=60, tool_result_max_chars=1000, llm_timeout_sec=5))
    assert result.stop_reason == "max_rounds" and result.reply == "Что успел"
    assert llm.calls[-1]["tools"] == llm.calls[0]["tools"] and llm.calls[-1]["tool_choice"] == "none"
    assert llm.calls[0]["tool_choice"] == "auto"
    assert llm.calls[-1]["messages"][-1] == {"role": "user", "content": FINAL_ANSWER_INSTRUCTION}
    assert len(result.steps) == 2


async def test_deadline_stops_loop():
    clock = FakeClock()

    async def slow_first(_messages, _tools):
        clock.now = 100.0
        return call("echo", {"value": "a"})

    llm = ScriptedLLM([slow_first, text("По собранному")])
    result = await _turn(llm, clock=clock)
    assert result.stop_reason == "deadline" and result.reply == "По собранному"
    assert llm.calls[-1]["tools"] and llm.calls[-1]["tool_choice"] == "none"


async def test_first_call_timeout_raises():
    async def never(_messages, _tools):
        await asyncio.sleep(1)
        return text("поздно")

    with pytest.raises(TurnDeadlineError):
        await _turn(ScriptedLLM([never]), config=LoopConfig(max_rounds=5, deadline_sec=0.05, tool_result_max_chars=1000, llm_timeout_sec=5))


async def test_llm_error_on_first_round_raises():
    with pytest.raises(LLMError):
        await _turn(ScriptedLLM([LLMError("down")]))


async def test_llm_error_after_tools_returns_partial_reply():
    result = await _turn(ScriptedLLM([call("echo", {"value": "a"}), LLMError("down")]))
    assert result.stop_reason == "llm_unavailable"
    assert "Модель недоступна" in result.reply and "echo: OK" in result.reply


async def test_unexpected_tool_exception_goes_back_to_model(caplog):
    llm = ScriptedLLM([call("crash", {"value": "secret-arg"}), text("Обошёл")])
    with caplog.at_level(logging.ERROR, logger="datalens_neuro.tools"):
        result = await _turn(llm, registry=CRASH_REGISTRY)
    assert result.steps[0].status == "INTERNAL" and result.reply == "Обошёл"
    content = llm.calls[1]["messages"][-1]["content"]
    payload = json.loads(content)
    assert payload["error"] == {"code": "INTERNAL", "message": "Tool failed"}
    assert "KeyError" not in content
    assert "tool failed" in caplog.text and "tool=crash" in caplog.text and "secret-arg" not in caplog.text


async def test_llm_error_after_tools_is_logged_with_category(caplog):
    with caplog.at_level(logging.WARNING, logger="datalens_neuro.llm"):
        await _turn(ScriptedLLM([call("echo", {"value": "a"}), LLMError("http_503")]))
    assert "reason=http_503" in caplog.text and "trace_id=" in caplog.text


async def test_final_call_llm_error_is_logged_with_category(caplog):
    llm = ScriptedLLM([call("echo", {"value": "a"}), LLMError("timeout")])
    with caplog.at_level(logging.WARNING, logger="datalens_neuro.llm"):
        result = await _turn(llm, config=LoopConfig(max_rounds=1, deadline_sec=60, tool_result_max_chars=1000, llm_timeout_sec=5))
    assert result.stop_reason == "llm_unavailable" and "reason=timeout" in caplog.text


async def test_tool_result_is_truncated():
    llm = ScriptedLLM([call("big", {"value": "a"}), text("ok")])
    await _turn(llm)
    content = llm.calls[1]["messages"][-1]["content"]
    assert len(content) <= 1000 and content.endswith("narrow the request]")


def test_truncate_short_text_unchanged():
    assert truncate("abc", 10) == "abc"
