from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.config import get_settings
from app.errors import ApiError, raise_from_us


class UsClient:
    def __init__(self, base_url: str, master_token: str, tenant_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._master_token = master_token
        self._tenant_id = tenant_id

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
            "x-us-master-token": self._master_token,
            "x-dl-tenant-id": self._tenant_id,
            "x-request-id": request_id,
            "accept": "application/json",
        }
        if headers:
            merged_headers.update(headers)
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
                response = await client.request(
                    method,
                    path,
                    params=_drop_none(params),
                    json=json,
                    headers=merged_headers,
                )
        except httpx.RequestError as exc:
            raise ApiError(500, "INTERNAL", f"US request failed: {exc}") from exc
        if response.status_code >= 400:
            try:
                payload: dict | str = response.json()
            except ValueError:
                payload = response.text
            raise_from_us(response.status_code, payload)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


def get_us_client() -> UsClient:
    settings = get_settings()
    return UsClient(settings.us_host, settings.us_master_token, settings.us_tenant_id)


def _drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
