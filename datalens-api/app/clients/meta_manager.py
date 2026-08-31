from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.clients.auth import get_user_access_token
from app.config import get_settings
from app.errors import ApiError, raise_from_us


class MetaManagerClient:
    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token

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
        request_id = trace_id or str(uuid.uuid4())
        merged_headers = {
            "Authorization": f"Bearer {self._access_token}",
            "x-request-id": request_id,
            "accept": "application/json",
        }
        if headers:
            merged_headers.update(headers)
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=60.0) as client:
                response = await client.request(
                    method,
                    path,
                    params=_drop_none(params),
                    json=json,
                    headers=merged_headers,
                )
        except httpx.RequestError as exc:
            raise ApiError(500, "INTERNAL", f"meta-manager request failed: {exc}") from exc
        if response.status_code >= 400:
            try:
                payload: dict | str = response.json()
            except ValueError:
                payload = response.text
            raise_from_us(response.status_code, payload)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


async def get_meta_manager_client() -> MetaManagerClient:
    settings = get_settings()
    token = await get_user_access_token()
    return MetaManagerClient(settings.meta_manager_host, token)


def _drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
