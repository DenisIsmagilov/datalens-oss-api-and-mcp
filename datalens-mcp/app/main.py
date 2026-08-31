from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.auth import BearerAuthMiddleware
from app.server import build_mcp


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_http_app() -> Starlette:
    application = build_mcp().streamable_http_app()
    application.routes.append(Route("/health", health))
    application.add_middleware(BearerAuthMiddleware)
    return application


app = create_http_app()
