import httpx
import pytest
import respx

from app.clients.meta_manager import MetaManagerClient, get_meta_manager_client
from app.errors import ApiError

META_HOST = "http://meta-manager.example:8080"


@pytest.mark.asyncio
@respx.mock
async def test_meta_manager_401_is_api_error():
    respx.post(f"{META_HOST}/workbooks/export").mock(
        return_value=httpx.Response(
            401,
            json={
                "code": "META_MANAGER.AUTH.UNAUTHORIZED_ACCESS",
                "message": "Unauthorized",
            },
        )
    )
    client = MetaManagerClient(base_url=META_HOST, access_token="t")
    with pytest.raises(ApiError) as exc:
        await client.request("POST", "/workbooks/export", json={"workbookId": "wb"})
    assert exc.value.status_code == 401
    assert exc.value.code == "UNAUTHENTICATED"


@pytest.mark.asyncio
@respx.mock
async def test_meta_manager_200_returns_json():
    respx.post(f"{META_HOST}/workbooks/export").mock(
        return_value=httpx.Response(200, json={"exportId": "exp1234567890"})
    )
    client = MetaManagerClient(base_url=META_HOST, access_token="t")
    body = await client.request("POST", "/workbooks/export", json={"workbookId": "wb"})
    assert body == {"exportId": "exp1234567890"}


@pytest.mark.asyncio
@respx.mock
async def test_meta_manager_timeout_is_60s(monkeypatch):
    captured: dict = {}
    real_client = httpx.AsyncClient

    def capturing_async_client(*args, **kwargs):
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(
        "app.clients.meta_manager.httpx.AsyncClient", capturing_async_client
    )
    respx.post(f"{META_HOST}/workbooks/export").mock(
        return_value=httpx.Response(200, json={"exportId": "e1"})
    )
    client = MetaManagerClient(base_url=META_HOST, access_token="t")
    await client.request("POST", "/workbooks/export", json={"workbookId": "wb"})
    assert captured["timeout"] == 60.0


@pytest.mark.asyncio
@respx.mock
async def test_meta_manager_sends_bearer_jwt_and_request_id():
    route = respx.post(f"{META_HOST}/workbooks/export").mock(
        return_value=httpx.Response(200, json={"exportId": "e1"})
    )
    client = MetaManagerClient(base_url=META_HOST, access_token="test-user-jwt")
    await client.request(
        "POST",
        "/workbooks/export",
        json={"workbookId": "wb"},
        trace_id="trace-mm-1",
    )
    headers = route.calls[0].request.headers
    assert headers["authorization"] == "Bearer test-user-jwt"
    assert headers["x-request-id"] == "trace-mm-1"


@pytest.mark.asyncio
@respx.mock
async def test_meta_manager_empty_body_is_object():
    respx.post(f"{META_HOST}/workbooks/export/e1/cancel").mock(
        return_value=httpx.Response(204)
    )
    client = MetaManagerClient(base_url=META_HOST, access_token="t")
    body = await client.request("POST", "/workbooks/export/e1/cancel")
    assert body == {}


@pytest.mark.asyncio
@respx.mock
async def test_meta_manager_409_stays_already_exists():
    respx.get(f"{META_HOST}/workbooks/export/e1/result").mock(
        return_value=httpx.Response(
            409,
            json={
                "code": "META_MANAGER.WORKBOOK_EXPORT_NOT_COMPLETED",
                "message": "The export is not completed. It is either still in progress or has failed",
            },
        )
    )
    client = MetaManagerClient(base_url=META_HOST, access_token="t")
    with pytest.raises(ApiError) as exc:
        await client.request("GET", "/workbooks/export/e1/result")
    assert exc.value.status_code == 409
    assert exc.value.code == "ALREADY_EXISTS"


@pytest.mark.asyncio
@respx.mock
async def test_get_meta_manager_client_uses_settings_and_jwt():
    respx.post("http://auth.example:8080/signin").mock(
        return_value=httpx.Response(200, json={"accessToken": "factory-jwt"})
    )
    route = respx.post(f"{META_HOST}/workbooks/export").mock(
        return_value=httpx.Response(200, json={"exportId": "e1"})
    )
    client = await get_meta_manager_client()
    await client.request("POST", "/workbooks/export", json={"workbookId": "wb"})
    assert route.calls[0].request.headers["authorization"] == "Bearer factory-jwt"
