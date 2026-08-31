from fastapi import Depends, FastAPI

from app.auth import AuthContext, require_auth
from app.config import get_settings
from app.errors import register_exception_handlers
from app.registry import unknown_method


def create_app() -> FastAPI:
    get_settings()
    app = FastAPI(title="DataLens API", version="2")
    register_exception_handlers(app)

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
