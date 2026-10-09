import json

import httpx
import pytest
import respx

from app.clients.datalens_api import DatalensApiClient, DatalensApiError
from app.request_context import reset_request_id, set_request_id

API = "http://datalens-api.example:8393"


@pytest.fixture
async def client():
    instance = DatalensApiClient(API, "dl-token", timeout_sec=5)
    yield instance
    await instance.aclose()


@respx.mock
async def test_rpc_sends_token_and_request_id(client):
    route = respx.post(f"{API}/rpc/getDataset").mock(return_value=httpx.Response(200, json={"id": "ds1"}))
    token = set_request_id("trace-9")
    try:
        body = await client.rpc("getDataset", {"datasetId": "ds1"})
    finally:
        reset_request_id(token)
    assert body == {"id": "ds1"}
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer dl-token"
    assert request.headers["x-request-id"] == "trace-9"
    assert json.loads(request.content) == {"datasetId": "ds1"}


@respx.mock
async def test_error_body_is_mapped(client):
    respx.post(f"{API}/rpc/queryDataset").mock(
        return_value=httpx.Response(
            400,
            json={"code": "INVALID_ARGUMENT", "message": "Unknown field", "details": {"availableFields": ["A"]}},
        )
    )
    with pytest.raises(DatalensApiError) as exc:
        await client.rpc("queryDataset", {})
    assert (exc.value.status_code, exc.value.code, exc.value.message) == (400, "INVALID_ARGUMENT", "Unknown field")
    assert exc.value.details == {"availableFields": ["A"]}


@respx.mock
async def test_non_json_error_is_internal(client):
    respx.post(f"{API}/rpc/getDashboard").mock(return_value=httpx.Response(502, text="Bad gateway"))
    with pytest.raises(DatalensApiError) as exc:
        await client.rpc("getDashboard", {})
    assert (exc.value.status_code, exc.value.code) == (502, "INTERNAL")


@respx.mock
async def test_timeout_is_deadline_exceeded(client):
    respx.post(f"{API}/rpc/getChartData").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(DatalensApiError) as exc:
        await client.rpc("getChartData", {})
    assert (exc.value.status_code, exc.value.code) == (504, "DEADLINE_EXCEEDED")
    assert exc.value.details == {"timeoutSec": 5}


@respx.mock
async def test_connect_error_is_unavailable(client):
    respx.post(f"{API}/rpc/getDataset").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(DatalensApiError) as exc:
        await client.rpc("getDataset", {})
    assert (exc.value.status_code, exc.value.code) == (502, "UNAVAILABLE")
