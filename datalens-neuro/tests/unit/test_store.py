from datetime import timedelta

import pytest

from app.models import Step
from app.store import Store, utc_now


@pytest.fixture
async def store(tmp_path):
    instance = Store(str(tmp_path / "db" / "neuro.sqlite"))
    await instance.open()
    yield instance
    await instance.close()


async def test_conversation_roundtrip(store):
    conversation = await store.create_conversation("default", "tg:1")
    assert conversation.id.startswith("c_") and len(conversation.id) == 22
    assert await store.get_conversation(conversation.id) == conversation
    assert await store.get_conversation("c_" + "0" * 20) is None


async def test_history_returns_last_messages_in_order(store):
    conversation = await store.create_conversation("default", None)
    for index in range(5):
        await store.add_message(conversation.id, "user", f"q{index}")
        await store.add_message(conversation.id, "assistant", f"a{index}", stop_reason="answer")
    assert await store.history(conversation.id, 3) == [
        {"role": "assistant", "content": "a3"},
        {"role": "user", "content": "q4"},
        {"role": "assistant", "content": "a4"},
    ]
    assert await store.history(conversation.id, 0) == []


async def test_detail_contains_steps(store):
    conversation = await store.create_conversation("default", None)
    await store.add_message(conversation.id, "user", "q", trace_id="t1")
    message_id = await store.add_message(
        conversation.id, "assistant", "a", stop_reason="answer", trace_id="t1"
    )
    await store.add_tool_calls(
        message_id,
        [Step(tool="query_dataset", args={"datasetId": "ds1"}, status="OK", duration_ms=12, row_count=3)],
        "t1",
    )
    detail = await store.conversation_detail(conversation.id)
    assert detail["pack"] == "default"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["steps"] == []
    assert detail["messages"][1]["steps"] == [
        {"tool": "query_dataset", "args": {"datasetId": "ds1"}, "status": "OK", "durationMs": 12, "rowCount": 3}
    ]
    assert detail["messages"][1]["traceId"] == "t1"
    assert detail["messages"][1]["stopReason"] == "answer"
    assert await store.conversation_detail("c_" + "1" * 20) is None


async def test_purge_removes_old_conversations_with_messages(store):
    old = await store.create_conversation("default", None)
    await store.add_message(old.id, "user", "q")
    assert await store.purge_older_than(30) == 0
    assert await store.purge_older_than(30, now=utc_now() + timedelta(days=31)) == 1
    assert await store.get_conversation(old.id) is None
    assert await store.history(old.id, 10) == []


async def test_data_survives_reopen(tmp_path):
    path = str(tmp_path / "neuro.sqlite")
    first = Store(path)
    await first.open()
    conversation = await first.create_conversation("default", None)
    await first.close()
    second = Store(path)
    await second.open()
    assert await second.get_conversation(conversation.id) is not None
    assert await second.ping() is True
    await second.close()


async def test_closed_store_raises(tmp_path):
    with pytest.raises(RuntimeError):
        await Store(str(tmp_path / "x.sqlite")).history("c_x", 1)


async def test_thread_idle_and_missing_conversation(store):
    conversation = await store.create_conversation("default", "dl:u1")
    moment = utc_now()
    await store.bind_thread("u1", conversation.id, now=moment)
    assert await store.current_thread("u1", 6, now=moment + timedelta(hours=5)) == conversation.id
    assert await store.current_thread("u1", 6, now=moment + timedelta(hours=6, seconds=1)) is None
    await store.bind_thread("u1", conversation.id, now=moment)
    await store._conn.execute("DELETE FROM conversations WHERE id = ?", (conversation.id,))
    await store._conn.commit()
    assert await store.current_thread("u1", 6, now=moment) is None


async def test_clear_thread(store):
    conversation = await store.create_conversation("default", "dl:u1")
    await store.bind_thread("u1", conversation.id)
    await store.clear_thread("u1")
    assert await store.current_thread("u1", 6) is None
    assert await store.get_conversation(conversation.id) is not None


async def test_formula_thread_is_independent(store):
    dash = await store.create_conversation("demo", "dl:u1")
    formula = await store.create_conversation("demo", "dl:u1")
    await store.bind_thread("u1", dash.id)
    await store.bind_formula_thread("u1", formula.id)
    assert await store.current_thread("u1", 6) == dash.id
    assert await store.current_formula_thread("u1", 6) == formula.id
    await store.clear_formula_thread("u1")
    assert await store.current_formula_thread("u1", 6) is None
    assert await store.current_thread("u1", 6) == dash.id
    assert await store.get_conversation(formula.id) is not None


async def test_formula_thread_idle_does_not_clear_dashboard_thread(store):
    dash = await store.create_conversation("demo", "dl:u1")
    formula = await store.create_conversation("demo", "dl:u1")
    moment = utc_now()
    await store.bind_formula_thread("u1", formula.id, now=moment)
    await store.bind_thread("u1", dash.id, now=moment + timedelta(hours=5, minutes=59))
    after_idle = moment + timedelta(hours=6, seconds=1)
    assert await store.current_formula_thread("u1", 6, now=after_idle) is None
    assert await store.current_thread("u1", 6, now=after_idle) == dash.id
    await store.bind_formula_thread("u1", formula.id, now=moment)
    await store._conn.execute("DELETE FROM conversations WHERE id = ?", (formula.id,))
    await store._conn.commit()
    assert await store.current_formula_thread("u1", 6, now=moment) is None
    assert await store.current_thread("u1", 6, now=moment) == dash.id


async def test_message_sources_roundtrip(store):
    conversation = await store.create_conversation("default", None)
    await store.add_message(
        conversation.id, "assistant", "ответ", sources=[{"type": "dataset", "id": "ds1"}]
    )
    detail = await store.conversation_detail(conversation.id)
    assert detail["messages"][0]["sources"] == [{"type": "dataset", "id": "ds1"}]


async def test_open_migrates_schema_without_sources_column(tmp_path):
    path = tmp_path / "old.sqlite"
    import aiosqlite

    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id TEXT, role TEXT,"
            " content TEXT, stop_reason TEXT, trace_id TEXT, created_at TEXT)"
        )
        await db.execute("PRAGMA user_version=1")
        await db.commit()
    store = Store(str(path))
    await store.open()
    async with store._conn.execute("PRAGMA table_info(messages)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}
    async with store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ui_threads'"
    ) as cursor:
        table = await cursor.fetchone()
    async with store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ui_formula_threads'"
    ) as cursor:
        formula_table = await cursor.fetchone()
    await store.close()
    assert "sources" in columns and table is not None
    assert formula_table is not None
