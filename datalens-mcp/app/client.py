from typing import Any

import httpx

from app.config import get_settings

_client: httpx.AsyncClient | None = None


def _api_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.dl_api_token}",
        "x-dl-api-version": settings.datalens_api_version,
    }


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=get_settings().datalens_api_timeout_sec)
    return _client


async def call_rpc(method: str, args: dict) -> tuple[int, Any]:
    settings = get_settings()
    url = f"{settings.datalens_api_host.rstrip('/')}/rpc/{method}"
    response = await _get_client().post(url, json=args, headers=_api_headers())
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return response.status_code, body


async def get_json_paths() -> list[str]:
    settings = get_settings()
    url = f"{settings.datalens_api_host.rstrip('/')}/json/"
    response = await _get_client().get(url, headers=_api_headers())
    if response.status_code != 200:
        # Non-200: return [] so list_rpc_methods keeps a stable tool JSON shape.
        return []
    try:
        data = response.json()
    except ValueError:
        return []
    paths = data.get("paths", {})
    return [path for path in paths if path.startswith("/rpc/")]


async def list_rpc_paths() -> list[str]:
    return await get_json_paths()
