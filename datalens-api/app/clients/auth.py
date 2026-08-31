from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

import httpx

from app.config import get_settings
from app.errors import ApiError, raise_from_us


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


async def get_user_access_token() -> str:
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
