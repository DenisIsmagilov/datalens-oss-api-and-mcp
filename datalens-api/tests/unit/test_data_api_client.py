import httpx
import pytest
import respx

from app.clients.data_api import DataApiClient, get_data_api_client
from app.errors import ApiError

DATA = "http://data-api.example:8080"
SIGNIN = "http://auth.example:8080/signin"


def _client(**kwargs) -> DataApiClient:
    return DataApiClient(DATA, "jwt", timeout_sec=5, **kwargs)


@pytest.mark.asyncio
@respx.mock
async def test_sends_bearer_and_request_id():
    route = respx.get(f"{DATA}/api/data/v2/datasets/ds1/fields").mock(
        return_value=httpx.Response(200, json={"fields": []})
    )
    assert await _client().get("/api/data/v2/datasets/ds1/fields") == {"fields": []}
    headers = route.calls[0].request.headers
    assert headers["authorization"] == "Bearer jwt"
    assert headers["x-request-id"]


@pytest.mark.asyncio
@respx.mock
async def test_db_error_details_are_dropped():
    respx.post(f"{DATA}/api/data/v2/datasets/ds1/result").mock(
        return_value=httpx.Response(
            400,
            json={
                "code": "ERR.DS_API.DB",
                "message": "Database error.",
                "details": {"query": "SELECT secret", "db_message": "boom"},
                "debug": {"query": "SELECT secret"},
            },
        )
    )
    with pytest.raises(ApiError) as exc:
        await _client().post("/api/data/v2/datasets/ds1/result", {})
    assert exc.value.status_code == 400
    assert exc.value.code == "INVALID_ARGUMENT"
    assert exc.value.details == {"code": "ERR.DS_API.DB"}
    assert "SELECT" not in exc.value.message


@pytest.mark.asyncio
@respx.mock
async def test_unknown_dataset_is_not_found():
    respx.get(f"{DATA}/api/data/v2/datasets/zz/fields").mock(
        return_value=httpx.Response(
            400, json={"code": "ERR.DS_API.US.VALIDATION_FAILED", "message": "x", "details": {"entry_id": "zz"}}
        )
    )
    with pytest.raises(ApiError) as exc:
        await _client().get("/api/data/v2/datasets/zz/fields")
    assert exc.value.status_code == 404 and exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
@respx.mock
async def test_formula_error_keeps_code_and_message():
    respx.post(f"{DATA}/api/data/v2/datasets/ds1/result").mock(
        return_value=httpx.Response(
            400,
            json={"code": "ERR.DS_API.FORMULA.PARSE.UNEXPECTED_EOF", "message": "Failed to parse", "details": {}, "debug": {}},
        )
    )
    with pytest.raises(ApiError) as exc:
        await _client().post("/api/data/v2/datasets/ds1/result", {})
    assert exc.value.message == "Failed to parse"
    assert exc.value.details == {"code": "ERR.DS_API.FORMULA.PARSE.UNEXPECTED_EOF"}


@pytest.mark.asyncio
@respx.mock
async def test_server_error_is_internal():
    respx.post(f"{DATA}/x").mock(return_value=httpx.Response(500, json={"code": "ERR.DS_API", "message": "Internal Server Error"}))
    client = _client()
    with pytest.raises(ApiError) as exc:
        await client.post("/x", {})
    assert exc.value.status_code == 500 and exc.value.code == "INTERNAL"
    assert exc.value.details == {}
    assert client.last_status == 500


@pytest.mark.asyncio
@respx.mock
async def test_long_backend_message_is_clipped():
    respx.post(f"{DATA}/x").mock(
        return_value=httpx.Response(400, json={"code": "ERR.DS_API.X", "message": "m" * 2000})
    )
    with pytest.raises(ApiError) as exc:
        await _client().post("/x", {})
    assert len(exc.value.message) <= 500


@pytest.mark.asyncio
@respx.mock
async def test_timeout_is_deadline_exceeded():
    respx.post(f"{DATA}/x").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ApiError) as exc:
        await _client().post("/x", {})
    assert exc.value.status_code == 504
    assert exc.value.code == "DEADLINE_EXCEEDED"
    assert exc.value.details == {"timeoutSec": 5}


@pytest.mark.asyncio
@respx.mock
async def test_401_refreshes_token_once_then_internal():
    respx.post(SIGNIN).mock(
        side_effect=[
            httpx.Response(200, json={"accessToken": "old"}),
            httpx.Response(200, json={"accessToken": "new"}),
        ]
    )
    route = respx.get(f"{DATA}/x").mock(return_value=httpx.Response(401, json={"message": "no"}))
    client = await get_data_api_client()
    with pytest.raises(ApiError) as exc:
        await client.get("/x")
    assert [c.request.headers["authorization"] for c in route.calls] == ["Bearer old", "Bearer new"]
    assert exc.value.status_code == 500 and exc.value.code == "INTERNAL"
