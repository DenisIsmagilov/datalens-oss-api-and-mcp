import httpx
import pytest
import respx

from app.clients.control_api import ControlApiClient, get_control_api_client
from app.errors import ApiError


@pytest.mark.asyncio
@respx.mock
async def test_control_api_sends_bearer_jwt():
    route = respx.get("http://control-api.example:8080/api/v1/connections/abc").mock(
        return_value=httpx.Response(200, json={"id": "abc", "type": "clickhouse"})
    )
    client = ControlApiClient(
        base_url="http://control-api.example:8080",
        access_token="test-user-jwt",
    )
    body = await client.request("GET", "/api/v1/connections/abc")
    assert body["id"] == "abc"
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@pytest.mark.asyncio
@respx.mock
async def test_control_api_maps_404():
    respx.get("http://control-api.example:8080/api/v1/connections/missing").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    client = ControlApiClient(
        base_url="http://control-api.example:8080",
        access_token="t",
    )
    with pytest.raises(ApiError) as exc:
        await client.request("GET", "/api/v1/connections/missing")
    assert exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
@respx.mock
async def test_control_api_empty_body_is_object():
    respx.delete("http://control-api.example:8080/api/v1/connections/abc").mock(
        return_value=httpx.Response(204)
    )
    client = ControlApiClient(
        base_url="http://control-api.example:8080",
        access_token="t",
    )
    body = await client.request("DELETE", "/api/v1/connections/abc")
    assert body == {}


@pytest.mark.asyncio
@respx.mock
async def test_control_api_connection_error_is_internal():
    respx.get("http://control-api.example:8080/api/v1/connections/abc").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    client = ControlApiClient(
        base_url="http://control-api.example:8080",
        access_token="t",
    )
    with pytest.raises(ApiError) as exc:
        await client.request("GET", "/api/v1/connections/abc")
    assert exc.value.status_code == 500
    assert exc.value.code == "INTERNAL"


@pytest.mark.asyncio
@respx.mock
async def test_get_control_api_client_uses_settings_and_jwt():
    respx.post("http://auth.example:8080/signin").mock(
        return_value=httpx.Response(200, json={"accessToken": "factory-jwt"})
    )
    route = respx.get("http://control-api.example:8080/api/v1/info/connectors").mock(
        return_value=httpx.Response(200, json={"connectors": []})
    )
    client = await get_control_api_client()
    await client.request("GET", "/api/v1/info/connectors")
    assert route.calls[0].request.headers["authorization"] == "Bearer factory-jwt"
