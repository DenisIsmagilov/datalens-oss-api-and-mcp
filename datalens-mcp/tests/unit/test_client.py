import pytest
import respx
from httpx import Response

from app.client import call_rpc, get_json_paths


@pytest.mark.asyncio
async def test_call_rpc_success():
    with respx.mock:
        route = respx.post(
            "http://datalens-api.example:8393/rpc/getWorkbooksList"
        ).mock(return_value=Response(200, json={"workbooks": []}))

        status, body = await call_rpc("getWorkbooksList", {"page": 0, "pageSize": 10})

        assert status == 200
        assert body == {"workbooks": []}
        assert route.called
        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer test-dl-token"
        assert request.headers["x-dl-api-version"] == "2"


@pytest.mark.asyncio
async def test_call_rpc_error_not_raises():
    with respx.mock:
        respx.post("http://datalens-api.example:8393/rpc/unknown").mock(
            return_value=Response(
                404, json={"code": "NOT_FOUND", "message": "x"}
            )
        )

        status, body = await call_rpc("unknown", {})

        assert status == 404
        assert body == {"code": "NOT_FOUND", "message": "x"}


@pytest.mark.asyncio
async def test_get_json_paths_error_not_raises():
    with respx.mock:
        respx.get("http://datalens-api.example:8393/json/").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        # Non-200 → [] (no raise); list_rpc_methods can attach error details in tool JSON.
        paths = await get_json_paths()

        assert paths == []
