import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.clients.datalens_api import DatalensApiClient
from app.config import Settings, get_settings
from app.errors import internal_error_response, register_exception_handlers
from app.formula.docs import load_docs
from app.formula.service import FormulaService
from app.llm.base import LLMProvider
from app.llm.factory import build_llm
from app.packs import PackRegistry, load_packs
from app.request_context import accept_request_id, reset_request_id, set_request_id
from app.routes import router
from app.service import ChatService, RateLimiter
from app.store import Store
from app.tools import build_registry
from app.ui_routes import router as ui_router

logger = logging.getLogger("datalens_neuro.errors")
_PURGE_INTERVAL_SEC = 86400


def configure_logging() -> None:
    root = logging.getLogger("datalens_neuro")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def _warn_on_startup(settings: Settings, llm: LLMProvider | None, packs: PackRegistry) -> None:
    log = logging.getLogger("datalens_neuro.startup")
    if not settings.neuro_api_token:
        log.warning("NEURO_API_TOKEN is empty: every request to /v1/* will be rejected with 401")
    if llm is None:
        log.warning("LLM is not configured: /v1/chat will answer 502 until LLM_* variables are set")
    if packs.get(settings.neuro_default_pack) is None:
        log.warning("default pack is missing: pack=%s", settings.neuro_default_pack)
    if settings.neuro_ui_enabled and not settings.auth_token_public_key:
        log.warning("AUTH_TOKEN_PUBLIC_KEY is empty: the panel will reject every session")


async def _purge_loop(store: Store, ttl_days: int) -> None:
    log = logging.getLogger("datalens_neuro.store")
    while True:
        try:
            removed = await store.purge_older_than(ttl_days)
            if removed:
                log.info("purged conversations=%d ttl_days=%d", removed, ttl_days)
        except Exception:
            log.exception("purge failed")
        await asyncio.sleep(_PURGE_INTERVAL_SEC)


def create_app(
    llm_factory: Callable[[Settings], LLMProvider | None] = build_llm,
    api_factory: Callable[[Settings], object] | None = None,
) -> FastAPI:
    configure_logging()
    cors_settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = get_settings()
        store = Store(settings.neuro_db_path)
        await store.open()
        packs = load_packs(settings.neuro_packs_dir)
        if api_factory is None:
            api = DatalensApiClient(
                settings.datalens_api_host, settings.dl_api_token, timeout_sec=settings.datalens_api_timeout_sec
            )
        else:
            api = api_factory(settings)
        llm = llm_factory(settings)
        _warn_on_startup(settings, llm, packs)
        docs = load_docs(Path("/app/formula-docs"))
        if not docs[1]:
            logging.getLogger("datalens_neuro.startup").warning(
                "formula docs have no fragments: path=/app/formula-docs"
            )
        limiter = RateLimiter(settings.neuro_rate_limit_per_min)
        app.state.store = store
        app.state.packs = packs
        app.state.service = ChatService(
            settings=settings,
            store=store,
            packs=packs,
            llm=llm,
            api=api,
            registry=build_registry(),
            limiter=limiter,
        )
        app.state.formula = FormulaService(
            settings=settings,
            store=store,
            packs=packs,
            llm=llm,
            api=api,
            limiter=limiter,
            docs=docs,
        )
        purge = asyncio.create_task(_purge_loop(store, settings.neuro_conversation_ttl_days))
        try:
            yield
        finally:
            purge.cancel()
            with suppress(asyncio.CancelledError):
                await purge
            api_close = getattr(api, "aclose", None)
            if api_close is not None:
                await api_close()
            llm_close = getattr(llm, "aclose", None)
            if llm_close is not None:
                await llm_close()
            await store.close()

    app = FastAPI(title="datalens-neuro", version="1", lifespan=lifespan)
    register_exception_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = accept_request_id(request.headers.get("x-request-id"))
        token = set_request_id(request_id)
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled error trace_id=%s", request_id)
                response = internal_error_response()
        finally:
            reset_request_id(token)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        db_ok = await request.app.state.store.ping()
        body = {
            "status": "ok" if db_ok else "degraded",
            "enabled": get_settings().neuro_enabled,
            "db": "ok" if db_ok else "error",
            "packs": len(request.app.state.packs.packs),
            "llmConfigured": request.app.state.service.llm_configured,
            "defaultPack": "ok" if request.app.state.packs.get(get_settings().neuro_default_pack) else "missing",
        }
        return JSONResponse(body, status_code=200 if db_ok else 503)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(cors_settings.ui_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "x-request-id"],
        expose_headers=["x-request-id"],
    )
    app.include_router(router)
    app.include_router(ui_router)
    return app


app = create_app()
