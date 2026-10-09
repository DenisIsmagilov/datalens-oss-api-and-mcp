import logging

from fastapi import Depends, FastAPI, Request

from app.auth import AuthContext, require_auth
from app.config import get_settings
from app.errors import internal_error_response, register_exception_handlers
from app.registry import unknown_method
from app.request_context import accept_request_id, reset_request_id, set_request_id

logger = logging.getLogger("datalens_api.errors")


def _configure_logging() -> None:
    root = logging.getLogger("datalens_api")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def create_app() -> FastAPI:
    _configure_logging()
    get_settings()
    app = FastAPI(title="DataLens API", version="2")
    register_exception_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = accept_request_id(request.headers.get("x-request-id"))
        token = set_request_id(request_id)
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                logger.exception("unhandled error trace_id=%s", request_id)
                response = internal_error_response(exc)
        finally:
            reset_request_id(token)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/json/")
    def openapi_json() -> dict:
        return app.openapi()

    # конкретные /rpc/* раньше catch-all — иначе Starlette матчит {method} первым
    from app.methods import register_all

    register_all(app)

    @app.post("/rpc/{method}", include_in_schema=False)
    async def rpc_fallback(
        method: str,
        _ctx: AuthContext = Depends(require_auth),
    ) -> None:
        await unknown_method(method)

    return app


app = create_app()
