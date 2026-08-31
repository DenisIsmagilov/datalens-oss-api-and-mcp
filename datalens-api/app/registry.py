from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, FastAPI

from app.auth import AuthContext, require_auth
from app.errors import ApiError

Handler = Callable[[Any, AuthContext], Awaitable[Any]]

_REGISTRY: dict[str, Handler] = {}


def list_methods() -> list[str]:
    return sorted(_REGISTRY)


def register_rpc(
    app: FastAPI,
    name: str,
    args_model: type,
    result_model: type,
    handler: Handler,
) -> None:
    _REGISTRY[name] = handler

    async def endpoint(
        args: args_model,  # type: ignore[valid-type]
        ctx: AuthContext = Depends(require_auth),
    ) -> result_model:  # type: ignore[valid-type]
        return await handler(args, ctx)

    app.add_api_route(
        f"/rpc/{name}",
        endpoint,
        methods=["POST"],
        response_model=result_model,
        response_model_exclude_unset=True,
        name=name,
        tags=[name],
    )


def reset_registry() -> None:
    _REGISTRY.clear()


async def unknown_method(method: str) -> None:
    raise ApiError(404, "NOT_FOUND", f"Unknown method: {method}")
