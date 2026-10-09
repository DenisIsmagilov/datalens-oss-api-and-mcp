from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.clients.auth import get_user_access_token, refresh_user_access_token
from app.config import get_settings
from app.errors import ApiError
from app.request_context import current_request_id

_NOT_FOUND_CODES = {"ERR.DS_API.US.VALIDATION_FAILED"}
_MAX_MESSAGE_CHARS = 500


def data_api_error(status_code: int, body: Any) -> ApiError:
    code = body.get("code") if isinstance(body, dict) else None
    message = body.get("message") if isinstance(body, dict) else None
    details = {"code": code} if code else {}
    if status_code == 404 or code in _NOT_FOUND_CODES:
        return ApiError(404, "NOT_FOUND", "Dataset not found", details)
    if status_code in (401, 403):
        return ApiError(500, "INTERNAL", "data-api service authorization failed")
    if status_code >= 500:
        return ApiError(500, "INTERNAL", "data-api internal error")
    if code and code.startswith("ERR.DS_API.DB"):
        return ApiError(400, "INVALID_ARGUMENT", "Database error", details)
    text = str(message or code or "data-api request failed")
    return ApiError(400, "INVALID_ARGUMENT", text[:_MAX_MESSAGE_CHARS], details)


class DataApiClient:
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

    async def get(self, path: str) -> dict:
        return await self._request("GET", path)

    async def post(self, path: str, json: Any) -> dict:
        return await self._request("POST", path, json)

    async def _request(self, method: str, path: str, json: Any = None) -> dict:
        response = await self._send(method, path, json)
        if response.status_code == 401 and self._refresh_token is not None:
            self._access_token = await self._refresh_token()
            response = await self._send(method, path, json)
        self.last_status = response.status_code
        if response.status_code >= 400:
            try:
                body: Any = response.json()
            except ValueError:
                body = None
            raise data_api_error(response.status_code, body)
        return response.json()

    async def _send(self, method: str, path: str, json: Any) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "x-request-id": current_request_id(),
            "accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout_sec
            ) as client:
                return await client.request(method, path, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            raise ApiError(
                504,
                "DEADLINE_EXCEEDED",
                "data-api request timed out",
                {"timeoutSec": self._timeout_sec},
            ) from exc
        except httpx.RequestError as exc:
            raise ApiError(
                500, "INTERNAL", f"data-api request failed: {type(exc).__name__}"
            ) from exc


async def get_data_api_client() -> DataApiClient:
    settings = get_settings()
    return DataApiClient(
        settings.data_api_host,
        await get_user_access_token(),
        timeout_sec=settings.data_query_timeout_sec,
        refresh_token=refresh_user_access_token,
    )
