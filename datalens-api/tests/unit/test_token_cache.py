import base64
import json
import time

import httpx
import pytest
import respx

from app.clients.auth import (
    get_user_access_token,
    invalidate_user_access_token,
    with_token_retry,
)
from app.clients.control_api import get_control_api_client
from app.errors import ApiError

SIGNIN = "http://auth.example:8080/signin"
CONTROL = "http://control-api.example:8080"


def _jwt(exp: float) -> str:
    def enc(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{enc({'alg': 'RS256'})}.{enc({'exp': exp, 'userId': 'u'})}.sig"


def _token(value: str) -> httpx.Response:
    return httpx.Response(200, json={"accessToken": value})


@pytest.mark.asyncio
@respx.mock
async def test_token_cached_until_exp_minus_margin():
    token = _jwt(time.time() + 900)
    route = respx.post(SIGNIN).mock(return_value=_token(token))
    assert await get_user_access_token() == token
    assert await get_user_access_token() == token
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_token_close_to_expiry_is_not_reused():
    route = respx.post(SIGNIN).mock(
        side_effect=[_token(_jwt(time.time() + 30)), _token("second")]
    )
    await get_user_access_token()
    assert await get_user_access_token() == "second"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_invalidate_forces_signin():
    route = respx.post(SIGNIN).mock(return_value=_token(_jwt(time.time() + 900)))
    await get_user_access_token()
    invalidate_user_access_token()
    await get_user_access_token()
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_with_token_retry_refreshes_once_on_401():
    respx.post(SIGNIN).mock(side_effect=[_token("old"), _token("new")])
    seen: list[str] = []

    async def call(token: str) -> str:
        seen.append(token)
        if token == "old":
            raise ApiError(401, "UNAUTHENTICATED", "expired")
        return "ok"

    assert await with_token_retry(call) == "ok"
    assert seen == ["old", "new"]


@pytest.mark.asyncio
@respx.mock
async def test_with_token_retry_ignores_other_errors():
    respx.post(SIGNIN).mock(return_value=_token("t"))
    calls = 0

    async def call(_token: str) -> str:
        nonlocal calls
        calls += 1
        raise ApiError(404, "NOT_FOUND", "missing")

    with pytest.raises(ApiError):
        await with_token_retry(call)
    assert calls == 1


@pytest.mark.asyncio
@respx.mock
async def test_control_api_client_retries_401_with_fresh_token():
    respx.post(SIGNIN).mock(side_effect=[_token("old"), _token("new")])
    route = respx.get(f"{CONTROL}/api/v1/info/connectors").mock(
        side_effect=[
            httpx.Response(401, json={"message": "expired"}),
            httpx.Response(200, json={"connectors": []}),
        ]
    )
    client = await get_control_api_client()
    assert await client.request("GET", "/api/v1/info/connectors") == {"connectors": []}
    assert [c.request.headers["authorization"] for c in route.calls] == [
        "Bearer old",
        "Bearer new",
    ]
