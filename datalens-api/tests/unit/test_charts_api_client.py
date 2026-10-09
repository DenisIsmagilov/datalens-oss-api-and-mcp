import json
from urllib.parse import unquote

import httpx
import pytest
import respx

from app.clients.charts_api import ChartsClient, get_charts_client
from app.errors import ApiError

UI = "http://ui.example:8080"
SIGNIN = "http://auth.example:8080/signin"


def _client() -> ChartsClient:
    return ChartsClient(UI, "jwt", timeout_sec=5)


@pytest.mark.asyncio
@respx.mock
async def test_run_sends_auth_cookie_and_body():
    route = respx.post(f"{UI}/api/run").mock(
        return_value=httpx.Response(200, json={"type": "table_wizard_node", "data": {}})
    )
    body = await _client().run("xyz789", {"a": ["1"]})
    assert body["type"] == "table_wizard_node"
    request = route.calls[0].request
    cookie = request.headers["cookie"]
    assert cookie.startswith("auth=")
    assert json.loads(unquote(cookie[len("auth=") :])) == {"accessToken": "jwt"}
    assert json.loads(request.content) == {"id": "xyz789", "params": {"a": ["1"]}}
    assert request.headers["x-request-id"]


@pytest.mark.asyncio
@respx.mock
async def test_unknown_chart_is_not_found():
    respx.post(f"{UI}/api/run").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": "ERR.CHARTS.CONFIG_LOADING_ERROR", "details": {"code": 400, "entryId": "zz"}}},
        )
    )
    with pytest.raises(ApiError) as exc:
        await _client().run("zz", {})
    assert exc.value.status_code == 404 and exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
@respx.mock
async def test_not_a_chart_is_invalid_argument():
    respx.post(f"{UI}/api/run").mock(return_value=httpx.Response(400, json={"error": "Unknown config type "}))
    with pytest.raises(ApiError) as exc:
        await _client().run("ds1", {})
    assert exc.value.code == "INVALID_ARGUMENT"
    assert exc.value.message == "Entry is not a chart"


@pytest.mark.asyncio
@respx.mock
async def test_data_fetching_error_drops_sql():
    respx.post(f"{UI}/api/run").mock(
        return_value=httpx.Response(
            427,
            json={
                "error": {
                    "code": "ERR.CHARTS.DATA_FETCHING_ERROR",
                    "details": {"sources": {"sql": {"data": {"sql_query": "SELECT secret"}}}},
                }
            },
        )
    )
    client = _client()
    with pytest.raises(ApiError) as exc:
        await client.run("c1", {})
    assert exc.value.status_code == 400
    assert exc.value.details == {"code": "ERR.CHARTS.DATA_FETCHING_ERROR"}
    assert "SELECT" not in exc.value.message
    assert client.last_status == 427


@pytest.mark.asyncio
@respx.mock
async def test_server_error_is_internal_without_details():
    respx.post(f"{UI}/api/run").mock(
        return_value=httpx.Response(
            500,
            json={"error": {"code": "ERR.CHARTS.INTERNAL", "details": {"sql": "secret"}}},
        )
    )
    client = _client()
    with pytest.raises(ApiError) as exc:
        await client.run("c1", {})
    assert exc.value.status_code == 500 and exc.value.code == "INTERNAL"
    assert exc.value.details == {}
    assert client.last_status == 500


@pytest.mark.asyncio
@respx.mock
async def test_timeout_is_deadline_exceeded():
    respx.post(f"{UI}/api/run").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ApiError) as exc:
        await _client().run("c1", {})
    assert exc.value.status_code == 504 and exc.value.code == "DEADLINE_EXCEEDED"


@pytest.mark.asyncio
@respx.mock
async def test_401_text_body_refreshes_once():
    respx.post(SIGNIN).mock(
        side_effect=[
            httpx.Response(200, json={"accessToken": "old"}),
            httpx.Response(200, json={"accessToken": "new"}),
        ]
    )
    route = respx.post(f"{UI}/api/run").mock(
        side_effect=[
            httpx.Response(401, text="Unauthorized access"),
            httpx.Response(200, json={"type": "metric2_ql_node", "data": []}),
        ]
    )
    client = await get_charts_client()
    assert (await client.run("m1", {}))["type"] == "metric2_ql_node"
    cookies = [json.loads(unquote(c.request.headers["cookie"][5:]))["accessToken"] for c in route.calls]
    assert cookies == ["old", "new"]
