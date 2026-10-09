from __future__ import annotations

import base64
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from urllib.parse import unquote

import httpx

from app.config import get_settings
from app.errors import ApiError, raise_from_us

T = TypeVar("T")

_EXPIRY_MARGIN_SEC = 60
_FALLBACK_TTL_SEC = 60
_cached_token: str | None = None
_cached_until: float = 0.0


def _token_from_cookie_value(raw: str) -> str | None:
    for candidate in (raw, unquote(raw)):
        try:
            data: Any = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("accessToken"):
            return str(data["accessToken"])
    return None


def _token_from_set_cookie(header: str) -> str | None:
    for segment in header.split(";"):
        segment = segment.strip()
        if segment.startswith("auth="):
            token = _token_from_cookie_value(segment[5:])
            if token:
                return token
    return None


def _token_from_signin(response: httpx.Response) -> str | None:
    cookie = response.cookies.get("auth")
    if cookie:
        token = _token_from_cookie_value(cookie)
        if token:
            return token
    set_cookie = response.headers.get("set-cookie")
    if set_cookie:
        token = _token_from_set_cookie(set_cookie)
        if token:
            return token
    try:
        body: Any = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and body.get("accessToken"):
        return str(body["accessToken"])
    return None


def _jwt_exp(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except ValueError:
        return None
    exp = data.get("exp") if isinstance(data, dict) else None
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None
    return float(exp)


async def _signin() -> str:
    settings = get_settings()
    url = f"{settings.auth_host.rstrip('/')}/signin"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json={"login": settings.auth_login, "password": settings.auth_password},
            )
    except httpx.RequestError as exc:
        raise ApiError(500, "INTERNAL", f"Auth signin failed: {exc}") from exc
    if response.status_code >= 400:
        try:
            payload: dict | str = response.json()
        except ValueError:
            payload = response.text
        raise_from_us(response.status_code, payload)
    token = _token_from_signin(response)
    if not token:
        raise ApiError(401, "UNAUTHENTICATED", "Auth signin did not return accessToken")
    return token


async def get_user_access_token() -> str:
    global _cached_token, _cached_until
    now = time.time()
    if _cached_token and now < _cached_until:
        return _cached_token
    token = await _signin()
    exp = _jwt_exp(token)
    _cached_token = token
    _cached_until = exp - _EXPIRY_MARGIN_SEC if exp else now + _FALLBACK_TTL_SEC
    return token


def invalidate_user_access_token() -> None:
    global _cached_token, _cached_until
    _cached_token = None
    _cached_until = 0.0


async def refresh_user_access_token() -> str:
    invalidate_user_access_token()
    return await get_user_access_token()


async def with_token_retry(call: Callable[[str], Awaitable[T]]) -> T:
    token = await get_user_access_token()
    try:
        return await call(token)
    except ApiError as exc:
        if exc.status_code != 401:
            raise
    return await call(await refresh_user_access_token())
