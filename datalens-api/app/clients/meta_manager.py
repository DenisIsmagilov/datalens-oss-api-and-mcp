from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.clients.auth import get_user_access_token, refresh_user_access_token
from app.config import get_settings
from app.errors import ApiError, raise_from_us
from app.request_context import current_request_id


class MetaManagerClient:
    def __init__(
        self,
        base_url: str,
        access_token: str,
        refresh_token: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token = refresh_token

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        trace_id: str | None = None,
    ) -> Any:
        request_id = trace_id or current_request_id()
        response = await self._send(method, path, params, json, headers, request_id)
        if response.status_code == 401 and self._refresh_token is not None:
            self._access_token = await self._refresh_token()
            response = await self._send(method, path, params, json, headers, request_id)
        if response.status_code >= 400:
            try:
                payload: dict | str = response.json()
            except ValueError:
                payload = response.text
            raise_from_us(response.status_code, payload)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def _send(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        json: Any,
        headers: dict[str, str] | None,
        request_id: str,
    ) -> httpx.Response:
        merged_headers = {
            "Authorization": f"Bearer {self._access_token}",
            "x-request-id": request_id,
            "accept": "application/json",
        }
        if headers:
            merged_headers.update(headers)
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=60.0) as client:
                return await client.request(
                    method,
                    path,
                    params=_drop_none(params),
                    json=json,
                    headers=merged_headers,
                )
        except httpx.RequestError as exc:
            raise ApiError(500, "INTERNAL", f"meta-manager request failed: {exc}") from exc


async def get_meta_manager_client() -> MetaManagerClient:
    settings = get_settings()
    token = await get_user_access_token()
    return MetaManagerClient(
        settings.meta_manager_host, token, refresh_token=refresh_user_access_token
    )


def _drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
