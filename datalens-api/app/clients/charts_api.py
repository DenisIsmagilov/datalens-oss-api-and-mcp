from __future__ import annotations

import json as jsonlib
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

import httpx

from app.clients.auth import get_user_access_token, refresh_user_access_token
from app.config import get_settings
from app.errors import ApiError
from app.request_context import current_request_id

_NOT_FOUND_CODE = "ERR.CHARTS.CONFIG_LOADING_ERROR"


def charts_error(status_code: int, body: Any) -> ApiError:
    error = body.get("error") if isinstance(body, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    details = {"code": code} if code else {}
    if status_code in (401, 403):
        return ApiError(500, "INTERNAL", "charts service authorization failed")
    if status_code == 404 or code == _NOT_FOUND_CODE:
        return ApiError(404, "NOT_FOUND", "Chart not found", details)
    if isinstance(error, str) and error.startswith("Unknown config type"):
        return ApiError(400, "INVALID_ARGUMENT", "Entry is not a chart")
    if status_code >= 500:
        return ApiError(500, "INTERNAL", "charts engine internal error")
    return ApiError(400, "INVALID_ARGUMENT", "Chart data fetching failed", details)


class ChartsClient:
    def __init__(
        self,
        base_url: str,
        access_token: str,
        *,
        timeout_sec: float,
        refresh_token: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._timeout_sec = timeout_sec
        self._refresh_token = refresh_token
        self.last_status: int | None = None

    async def run(self, chart_id: str, params: dict) -> dict:
        payload = {"id": chart_id, "params": params}
        response = await self._send(payload)
        if response.status_code == 401 and self._refresh_token is not None:
            self._access_token = await self._refresh_token()
            response = await self._send(payload)
        self.last_status = response.status_code
        if response.status_code >= 400:
            try:
                body: Any = response.json()
            except ValueError:
                body = None
            raise charts_error(response.status_code, body)
        return response.json()

    async def _send(self, payload: dict) -> httpx.Response:
        cookie = quote(jsonlib.dumps({"accessToken": self._access_token}), safe="")
        headers = {
            "cookie": f"auth={cookie}",
            "x-request-id": current_request_id(),
            "accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout_sec
            ) as client:
                return await client.post("/api/run", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ApiError(
                504,
                "DEADLINE_EXCEEDED",
                "charts engine request timed out",
                {"timeoutSec": self._timeout_sec},
            ) from exc
        except httpx.RequestError as exc:
            raise ApiError(
                500, "INTERNAL", f"charts engine request failed: {type(exc).__name__}"
            ) from exc


async def get_charts_client() -> ChartsClient:
    settings = get_settings()
    return ChartsClient(
        settings.charts_host,
        await get_user_access_token(),
        timeout_sec=settings.data_query_timeout_sec,
        refresh_token=refresh_user_access_token,
    )
