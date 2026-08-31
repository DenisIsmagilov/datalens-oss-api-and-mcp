import httpx
import pytest
import respx

from app.clients.us import UsClient
from app.errors import ApiError


@pytest.mark.asyncio
@respx.mock
async def test_us_client_sends_master_token_and_tenant():
    route = respx.get("http://us.example:8080/v2/workbooks").mock(
        return_value=httpx.Response(200, json={"workbooks": [], "nextPageToken": None})
    )
    client = UsClient(
        base_url="http://us.example:8080",
        master_token="test-us-master-token",
        tenant_id="common",
    )
    body = await client.request("GET", "/v2/workbooks", params={"page": 0})
    assert body["workbooks"] == []
    assert route.called
    headers = route.calls[0].request.headers
    assert headers["x-us-master-token"] == "test-us-master-token"
    assert headers["x-dl-tenant-id"] == "common"


@pytest.mark.asyncio
@respx.mock
async def test_us_client_maps_404():
    respx.get("http://us.example:8080/v2/workbooks/missing").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    client = UsClient(
        base_url="http://us.example:8080",
        master_token="t",
        tenant_id="common",
    )
    with pytest.raises(ApiError) as exc:
        await client.request("GET", "/v2/workbooks/missing")
    assert exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
@respx.mock
async def test_us_client_merges_extra_headers():
    route = respx.get("http://us.example:8080/v2/workbooks").mock(
        return_value=httpx.Response(200, json={"workbooks": []})
    )
    client = UsClient(
        base_url="http://us.example:8080",
        master_token="test-us-master-token",
        tenant_id="common",
    )
    await client.request(
        "GET",
        "/v2/workbooks",
        headers={"Authorization": "Bearer extra-jwt"},
    )
    headers = route.calls[0].request.headers
    assert headers["authorization"] == "Bearer extra-jwt"
    assert headers["x-us-master-token"] == "test-us-master-token"


@pytest.mark.asyncio
@respx.mock
async def test_us_client_connection_error_is_internal():
    respx.get("http://us.example:8080/v2/workbooks").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    client = UsClient(
        base_url="http://us.example:8080",
        master_token="t",
        tenant_id="common",
    )
    with pytest.raises(ApiError) as exc:
        await client.request("GET", "/v2/workbooks")
    assert exc.value.status_code == 500
    assert exc.value.code == "INTERNAL"

