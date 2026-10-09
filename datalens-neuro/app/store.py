import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.models import Step

SCHEMA_VERSION = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    pack TEXT NOT NULL,
    channel_user TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_by_updated ON conversations(updated_at);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    stop_reason TEXT,
    trace_id TEXT,
    created_at TEXT NOT NULL,
    sources TEXT
);
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    row_count INTEGER,
    trace_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tool_calls_by_message ON tool_calls(message_id);
CREATE TABLE IF NOT EXISTS ui_threads (
    user_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ui_formula_threads (
    user_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def new_conversation_id() -> str:
    return "c_" + secrets.token_hex(10)


@dataclass
class Conversation:
    id: str
    pack: str
    channel_user: str | None
    created_at: str
    updated_at: str


class Store:
    def __init__(self, path: str) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self._path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript(_SCHEMA)
        async with db.execute("PRAGMA table_info(messages)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if "sources" not in columns:
            await db.execute("ALTER TABLE messages ADD COLUMN sources TEXT")
        await db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        await db.commit()
        self._db = db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("store is not open")
        return self._db

    async def ping(self) -> bool:
        try:
            async with self._conn.execute("SELECT 1") as cursor:
                await cursor.fetchone()
        except Exception:
            return False
        return os.access(Path(self._path).parent, os.W_OK)

    async def create_conversation(self, pack: str, channel_user: str | None) -> Conversation:
        now = _iso(utc_now())
        conversation = Conversation(new_conversation_id(), pack, channel_user, now, now)
        await self._conn.execute(
            "INSERT INTO conversations (id, pack, channel_user, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (conversation.id, pack, channel_user, now, now),
        )
        await self._conn.commit()
        return conversation

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        async with self._conn.execute(
            "SELECT id, pack, channel_user, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Conversation(
            row["id"], row["pack"], row["channel_user"], row["created_at"], row["updated_at"]
        )

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        stop_reason: str | None = None,
        trace_id: str | None = None,
        sources: list | None = None,
    ) -> int:
        now = _iso(utc_now())
        cursor = await self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content, stop_reason, trace_id, created_at, sources)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                conversation_id,
                role,
                content,
                stop_reason,
                trace_id,
                now,
                json.dumps(sources, ensure_ascii=False) if sources else None,
            ),
        )
        message_id = int(cursor.lastrowid)
        await cursor.close()
        await self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
        )
        await self._conn.commit()
        return message_id

    async def add_tool_calls(self, message_id: int, steps: list[Step], trace_id: str | None) -> None:
        if not steps:
            return
        now = _iso(utc_now())
        await self._conn.executemany(
            "INSERT INTO tool_calls"
            " (message_id, tool, args, status, duration_ms, row_count, trace_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    message_id,
                    step.tool,
                    json.dumps(step.args, ensure_ascii=False, default=str),
                    step.status,
                    step.duration_ms,
                    step.row_count,
                    trace_id,
                    now,
                )
                for step in steps
            ],
        )
        await self._conn.commit()

    async def history(self, conversation_id: str, limit: int) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        async with self._conn.execute(
            "SELECT role, content FROM messages"
            " WHERE conversation_id = ? AND role IN ('user', 'assistant')"
            " ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    async def conversation_detail(self, conversation_id: str) -> dict[str, Any] | None:
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            return None
        async with self._conn.execute(
            "SELECT id, role, content, stop_reason, trace_id, created_at, sources FROM messages"
            " WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ) as cursor:
            messages = await cursor.fetchall()
        async with self._conn.execute(
            "SELECT t.message_id, t.tool, t.args, t.status, t.duration_ms, t.row_count"
            " FROM tool_calls t JOIN messages m ON m.id = t.message_id"
            " WHERE m.conversation_id = ? ORDER BY t.id",
            (conversation_id,),
        ) as cursor:
            calls = await cursor.fetchall()
        steps: dict[int, list[dict[str, Any]]] = {}
        for call in calls:
            steps.setdefault(call["message_id"], []).append(
                {
                    "tool": call["tool"],
                    "args": json.loads(call["args"]),
                    "status": call["status"],
                    "durationMs": call["duration_ms"],
                    "rowCount": call["row_count"],
                }
            )
        return {
            "conversationId": conversation.id,
            "pack": conversation.pack,
            "createdAt": conversation.created_at,
            "updatedAt": conversation.updated_at,
            "messages": [
                {
                    "role": message["role"],
                    "content": message["content"],
                    "stopReason": message["stop_reason"],
                    "traceId": message["trace_id"],
                    "createdAt": message["created_at"],
                    "steps": steps.get(message["id"], []),
                    "sources": json.loads(message["sources"]) if message["sources"] else [],
                }
                for message in messages
            ],
        }

    async def bind_thread(self, user_id: str, conversation_id: str, *, now: datetime | None = None) -> None:
        moment = _iso(now or utc_now())
        await self._conn.execute(
            "INSERT INTO ui_threads (user_id, conversation_id, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(user_id) DO UPDATE SET conversation_id = excluded.conversation_id,"
            " updated_at = excluded.updated_at",
            (user_id, conversation_id, moment),
        )
        await self._conn.commit()

    async def clear_thread(self, user_id: str) -> None:
        await self._conn.execute("DELETE FROM ui_threads WHERE user_id = ?", (user_id,))
        await self._conn.commit()

    async def current_thread(self, user_id: str, idle_hours: int, *, now: datetime | None = None) -> str | None:
        async with self._conn.execute(
            "SELECT conversation_id, updated_at FROM ui_threads WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        moment = now or utc_now()
        updated = datetime.fromisoformat(row["updated_at"])
        if moment - updated > timedelta(hours=idle_hours) or await self.get_conversation(row["conversation_id"]) is None:
            await self.clear_thread(user_id)
            return None
        return row["conversation_id"]

    async def bind_formula_thread(
        self, user_id: str, conversation_id: str, *, now: datetime | None = None
    ) -> None:
        moment = _iso(now or utc_now())
        await self._conn.execute(
            "INSERT INTO ui_formula_threads (user_id, conversation_id, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(user_id) DO UPDATE SET conversation_id = excluded.conversation_id,"
            " updated_at = excluded.updated_at",
            (user_id, conversation_id, moment),
        )
        await self._conn.commit()

    async def clear_formula_thread(self, user_id: str) -> None:
        await self._conn.execute("DELETE FROM ui_formula_threads WHERE user_id = ?", (user_id,))
        await self._conn.commit()

    async def current_formula_thread(
        self, user_id: str, idle_hours: int, *, now: datetime | None = None
    ) -> str | None:
        async with self._conn.execute(
            "SELECT conversation_id, updated_at FROM ui_formula_threads WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        moment = now or utc_now()
        updated = datetime.fromisoformat(row["updated_at"])
        if moment - updated > timedelta(hours=idle_hours) or await self.get_conversation(row["conversation_id"]) is None:
            await self.clear_formula_thread(user_id)
            return None
        return row["conversation_id"]

    async def purge_older_than(self, days: int, *, now: datetime | None = None) -> int:
        cutoff = _iso((now or utc_now()) - timedelta(days=days))
        cursor = await self._conn.execute("DELETE FROM conversations WHERE updated_at < ?", (cutoff,))
        removed = cursor.rowcount
        await cursor.close()
        await self._conn.commit()
        return removed
