import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.loop import LoopConfig, TurnDeadlineError, run_turn
from app.agent.prompt import build_system_prompt
from app.clients.datalens_api import DatalensApiClient
from app.config import Settings
from app.errors import NeuroError
from app.llm.base import LLMError, LLMProvider
from app.models import TurnResult
from app.packs import PackRegistry
from app.schemas import ChatRequest, ChatResponse, SourceOut, StepOut, UsageOut
from app.store import Store
from app.tools.base import ToolContext, ToolRegistry
from app.tools.scope_cache import ScopeCache

logger = logging.getLogger("datalens_neuro.turn")
llm_logger = logging.getLogger("datalens_neuro.llm")


class RateLimiter:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._swept_at = clock()

    def _sweep(self, now: float) -> None:
        for key in [key for key, hits in self._hits.items() if now - hits[-1] >= 60]:
            del self._hits[key]
        self._swept_at = now

    def allow(self, key: str) -> bool:
        if self._per_minute <= 0:
            return True
        now = self._clock()
        if now - self._swept_at >= 60:
            self._sweep(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= 60:
            hits.popleft()
        if len(hits) >= self._per_minute:
            return False
        hits.append(now)
        return True


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: Store,
        packs: PackRegistry,
        llm: LLMProvider | None,
        api: DatalensApiClient,
        registry: ToolRegistry,
        limiter: RateLimiter | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._packs = packs
        self._llm = llm
        self._api = api
        self._registry = registry
        self._now = now or (lambda: datetime.now(ZoneInfo(settings.neuro_timezone)))
        self._scope = ScopeCache()
        self._limiter = limiter if limiter is not None else RateLimiter(settings.neuro_rate_limit_per_min)
        self._locks: dict[str, asyncio.Lock] = {}
        self._config = LoopConfig(
            max_rounds=settings.neuro_max_rounds,
            deadline_sec=settings.neuro_deadline_sec,
            tool_result_max_chars=settings.neuro_tool_result_max_chars,
            llm_timeout_sec=settings.llm_timeout_sec,
        )

    @property
    def llm_configured(self) -> bool:
        return self._llm is not None

    def _log(
        self, *, trace_id: str, conversation_id: str, pack: str, status: str, started: float, result: TurnResult | None
    ) -> None:
        logger.info(
            "trace_id=%s conversation=%s pack=%s status=%s stop=%s rounds=%d tools=%s duration_ms=%d"
            " prompt_tokens=%d completion_tokens=%d",
            trace_id,
            conversation_id,
            pack,
            status,
            result.stop_reason if result else "-",
            result.rounds if result else 0,
            ",".join(f"{s.tool}:{s.status}" for s in result.steps) if result else "",
            int((time.monotonic() - started) * 1000),
            result.prompt_tokens if result else 0,
            result.completion_tokens if result else 0,
        )

    async def chat(self, request: ChatRequest, *, trace_id: str) -> ChatResponse:
        started = time.monotonic()
        channel_user = request.user.externalId if request.user else None
        if not self._limiter.allow(channel_user or "-"):
            raise NeuroError(
                429, "RESOURCE_EXHAUSTED", "Too many requests",
                {"limitPerMinute": self._settings.neuro_rate_limit_per_min},
            )
        if self._llm is None:
            raise NeuroError(502, "LLM_UNAVAILABLE", "LLM is not configured")

        conversation = None
        if request.conversationId:
            conversation = await self._store.get_conversation(request.conversationId)
            if conversation is None:
                raise NeuroError(404, "NOT_FOUND", "Conversation not found", {"conversationId": request.conversationId})
            if request.pack and request.pack != conversation.pack:
                raise NeuroError(
                    400, "INVALID_ARGUMENT", "Pack of an existing conversation cannot be changed",
                    {"pack": conversation.pack},
                )
            pack_name = conversation.pack
        else:
            pack_name = request.pack or self._settings.neuro_default_pack
        pack = self._packs.get(pack_name)
        if pack is None:
            raise NeuroError(
                404, "NOT_FOUND", "Pack not found",
                {"pack": pack_name, "reason": self._packs.errors.get(pack_name, "not installed")},
            )
        if conversation is None:
            conversation = await self._store.create_conversation(pack_name, channel_user)

        lock = self._locks.setdefault(conversation.id, asyncio.Lock())
        if lock.locked():
            raise NeuroError(409, "CONVERSATION_BUSY", "Another turn is in progress in this conversation")
        try:
            async with lock:
                history = await self._store.history(conversation.id, self._settings.neuro_history_messages)
                context = request.context.model_dump(exclude_none=True) if request.context else None
                try:
                    result = await run_turn(
                        llm=self._llm,
                        registry=self._registry,
                        ctx=ToolContext(api=self._api, pack=pack, scope=self._scope),
                        system_prompt=build_system_prompt(pack, context=context, now=self._now()),
                        history=history,
                        user_message=request.message,
                        config=self._config,
                    )
                except LLMError as exc:
                    self._log(trace_id=trace_id, conversation_id=conversation.id, pack=pack_name, status="LLM_UNAVAILABLE", started=started, result=None)
                    llm_logger.warning("llm unavailable trace_id=%s reason=%s", trace_id, exc.category)
                    raise NeuroError(502, "LLM_UNAVAILABLE", "LLM is unavailable", {"reason": exc.category}) from exc
                except TurnDeadlineError as exc:
                    self._log(trace_id=trace_id, conversation_id=conversation.id, pack=pack_name, status="DEADLINE_EXCEEDED", started=started, result=None)
                    raise NeuroError(
                        504, "DEADLINE_EXCEEDED", "No answer before the turn deadline",
                        {"deadlineSec": self._settings.neuro_deadline_sec},
                    ) from exc
                await self._store.add_message(conversation.id, "user", request.message, trace_id=trace_id)
                message_id = await self._store.add_message(
                    conversation.id,
                    "assistant",
                    result.reply,
                    stop_reason=result.stop_reason,
                    trace_id=trace_id,
                    sources=result.sources,
                )
                await self._store.add_tool_calls(message_id, result.steps, trace_id)
        finally:
            if not lock.locked():
                self._locks.pop(conversation.id, None)

        self._log(trace_id=trace_id, conversation_id=conversation.id, pack=pack_name, status="OK", started=started, result=result)
        return ChatResponse(
            conversationId=conversation.id,
            reply=result.reply,
            stopReason=result.stop_reason,
            steps=[
                StepOut(tool=s.tool, args=s.args, status=s.status, durationMs=s.duration_ms, rowCount=s.row_count)
                for s in result.steps
            ],
            sources=[SourceOut(**source) for source in result.sources],
            usage=UsageOut(rounds=result.rounds, promptTokens=result.prompt_tokens, completionTokens=result.completion_tokens),
        )
