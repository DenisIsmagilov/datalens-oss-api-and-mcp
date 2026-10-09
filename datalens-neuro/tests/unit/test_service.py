import asyncio

import pytest

from app.config import get_settings
from app.errors import NeuroError
from app.llm.base import LLMError
from app.packs import load_packs
from app.schemas import ChatRequest
from app.service import ChatService, RateLimiter
from app.store import Store
from app.tools import build_registry
from tests.fakes import ScriptedLLM, text


async def test_parallel_turn_in_same_conversation_is_busy(tmp_path):
    started, release = asyncio.Event(), asyncio.Event()

    async def slow(_messages, _tools):
        started.set()
        await release.wait()
        return text("готово")

    store = Store(str(tmp_path / "n.sqlite"))
    await store.open()
    service = ChatService(
        settings=get_settings(),
        store=store,
        packs=load_packs("/app/packs"),
        llm=ScriptedLLM([text("первый"), slow, text("другой диалог")]),
        api=None,
        registry=build_registry(),
    )
    first = await service.chat(ChatRequest(message="q"), trace_id="t0")
    task = asyncio.create_task(service.chat(ChatRequest(message="q2", conversationId=first.conversationId), trace_id="t1"))
    await started.wait()
    with pytest.raises(NeuroError) as exc:
        await service.chat(ChatRequest(message="q3", conversationId=first.conversationId), trace_id="t2")
    assert (exc.value.status_code, exc.value.code) == (409, "CONVERSATION_BUSY")
    other = await service.chat(ChatRequest(message="q4"), trace_id="t3")
    assert other.reply == "другой диалог"
    release.set()
    assert (await task).reply == "готово"
    await store.close()


async def test_new_conversation_of_failed_turn_stays_empty_and_locks_are_released(tmp_path):
    store = Store(str(tmp_path / "n.sqlite"))
    await store.open()
    try:
        service = ChatService(
            settings=get_settings(),
            store=store,
            packs=load_packs("/app/packs"),
            llm=ScriptedLLM([text("ок"), LLMError("timeout")]),
            api=None,
            registry=build_registry(),
        )
        ok = await service.chat(ChatRequest(message="q"), trace_id="t0")
        assert service._locks == {}
        with pytest.raises(NeuroError) as exc:
            await service.chat(ChatRequest(message="q2"), trace_id="t1")
        assert exc.value.status_code == 502 and exc.value.details == {"reason": "timeout"}
        assert service._locks == {}
        async with store._conn.execute(
            "SELECT c.id, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS n FROM conversations c"
        ) as cursor:
            counts = {row["id"]: row["n"] for row in await cursor.fetchall()}
        assert len(counts) == 2 and counts[ok.conversationId] == 2
        assert sorted(counts.values()) == [0, 2]
    finally:
        await store.close()


def test_rate_limiter_drops_idle_keys():
    now = [0.0]
    limiter = RateLimiter(2, clock=lambda: now[0])
    for key in ("a", "b", "c"):
        assert limiter.allow(key)
    now[0] = 61
    assert limiter.allow("d")
    assert set(limiter._hits) == {"d"}


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(2, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")
    now[0] = 61
    assert limiter.allow("a")
    assert RateLimiter(0).allow("x")
