from typing import Any

import httpx

from app.request_context import current_request_id


class DatalensApiError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class DatalensApiClient:
    def __init__(self, base_url: str, token: str, *, timeout_sec: float) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_sec)
        self._token = token
        self._timeout_sec = timeout_sec

    async def aclose(self) -> None:
        await self._client.aclose()

    async def rpc(self, method: str, args: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "x-request-id": current_request_id(),
            "accept": "application/json",
        }
        try:
            response = await self._client.post(f"/rpc/{method}", json=args, headers=headers)
        except httpx.TimeoutException as exc:
            raise DatalensApiError(
                504,
                "DEADLINE_EXCEEDED",
                f"datalens-api {method} timed out",
                {"timeoutSec": self._timeout_sec},
            ) from exc
        except httpx.RequestError as exc:
            raise DatalensApiError(
                502, "UNAVAILABLE", f"datalens-api unavailable: {type(exc).__name__}"
            ) from exc
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            if isinstance(body, dict) and body.get("code"):
                details = body.get("details")
                raise DatalensApiError(
                    response.status_code,
                    str(body["code"]),
                    str(body.get("message") or "")[:500],
                    details if isinstance(details, dict) else {},
                )
            raise DatalensApiError(
                response.status_code, "INTERNAL", f"datalens-api HTTP {response.status_code}"
            )
        if not isinstance(body, dict):
            raise DatalensApiError(502, "INTERNAL", "datalens-api returned a non-object body")
        return body
