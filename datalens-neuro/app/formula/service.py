import asyncio
import logging
import time
from typing import Any

from app.clients.datalens_api import DatalensApiError
from app.config import Settings
from app.errors import NeuroError
from app.formula.turn import run_formula_turn
from app.llm.base import LLMError, LLMProvider
from app.packs import PackRegistry
from app.schemas import ChatResponse, UsageOut
from app.service import RateLimiter
from app.store import Store

logger = logging.getLogger("datalens_neuro.formula")
_CHART_KINDS = {"wizard", "ql"}


class FormulaService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: Store,
        packs: PackRegistry,
        llm: LLMProvider | None,
        api: Any,
        limiter: RateLimiter,
        docs: tuple[str, list],
    ) -> None:
        self._settings = settings
        self._store = store
        self._packs = packs
        self._llm = llm
        self._api = api
        self._limiter = limiter
        self._docs = docs
        self._locks: dict[str, asyncio.Lock] = {}

    async def turn(
        self,
        message: str,
        chart_id: str | None,
        chart_kind: str | None,
        user_id: str,
        trace_id: str,
    ) -> ChatResponse:
        started = time.monotonic()
        channel_user = f"dl:{user_id}"
        if not self._limiter.allow(channel_user):
            raise NeuroError(
                429, "RESOURCE_EXHAUSTED", "Too many requests",
                {"limitPerMinute": self._settings.neuro_rate_limit_per_min},
            )
        if self._llm is None:
            raise NeuroError(502, "LLM_UNAVAILABLE", "LLM is not configured")
        if chart_id and chart_kind not in _CHART_KINDS:
            raise NeuroError(400, "INVALID_ARGUMENT", "chartKind is invalid")

        pack_name = self._settings.neuro_default_pack
        pack = self._packs.get(pack_name)
        if pack is None:
            raise NeuroError(
                404, "NOT_FOUND", "Pack not found",
                {"pack": pack_name, "reason": self._packs.errors.get(pack_name, "not installed")},
            )

        conversation_id = await self._store.current_formula_thread(
            user_id, self._settings.neuro_ui_conversation_idle_hours
        )
        if conversation_id is None:
            conversation = await self._store.create_conversation(pack_name, channel_user)
        else:
            conversation = await self._store.get_conversation(conversation_id)
            if conversation is None:
                conversation = await self._store.create_conversation(pack_name, channel_user)

        lock = self._locks.setdefault(conversation.id, asyncio.Lock())
        if lock.locked():
            raise NeuroError(409, "CONVERSATION_BUSY", "Another turn is in progress in this conversation")
        try:
            async with lock:
                history = await self._store.history(conversation.id, self._settings.neuro_history_messages)
                deadline_at = time.monotonic() + self._settings.neuro_deadline_sec
                try:
                    outcome = await run_formula_turn(
                        llm=self._llm,
                        api=self._api,
                        pack=pack,
                        docs=self._docs,
                        question=message,
                        chart_id=chart_id,
                        chart_kind=chart_kind,
                        history=history,
                        attempts=self._settings.neuro_formula_attempts,
                        fragment_limit=self._settings.neuro_formula_doc_fragments,
                        fragment_chars=self._settings.neuro_formula_doc_chars,
                        deadline_at=deadline_at,
                    )
                except LLMError as exc:
                    raise NeuroError(
                        502, "LLM_UNAVAILABLE", "LLM is unavailable", {"reason": exc.category}
                    ) from exc
                except DatalensApiError as exc:
                    if exc.status_code == 504:
                        raise NeuroError(
                            504, "DEADLINE_EXCEEDED", "No answer before the turn deadline",
                            {"deadlineSec": self._settings.neuro_deadline_sec},
                        ) from exc
                    raise NeuroError(502, "UNAVAILABLE", "DataLens API is unavailable") from exc
                await self._store.add_message(conversation.id, "user", message, trace_id=trace_id)
                await self._store.add_message(
                    conversation.id,
                    "assistant",
                    outcome.reply,
                    stop_reason=outcome.stop_reason,
                    trace_id=trace_id,
                )
                await self._store.bind_formula_thread(user_id, conversation.id)
        finally:
            if not lock.locked():
                self._locks.pop(conversation.id, None)

        logger.info(
            "trace_id=%s userId=%s conversationId=%s dataset_id=%s rounds=%d stop_reason=%s duration_ms=%d",
            trace_id,
            user_id,
            conversation.id,
            outcome.dataset_id or "-",
            outcome.rounds,
            outcome.stop_reason,
            int((time.monotonic() - started) * 1000),
        )
        return ChatResponse(
            conversationId=conversation.id,
            reply=outcome.reply,
            stopReason=outcome.stop_reason,
            steps=[],
            sources=[],
            usage=UsageOut(
                rounds=outcome.rounds,
                promptTokens=outcome.prompt_tokens,
                completionTokens=outcome.completion_tokens,
            ),
        )
