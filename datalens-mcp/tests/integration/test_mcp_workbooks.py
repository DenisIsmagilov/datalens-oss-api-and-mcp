import json
import os

import httpx
import pytest

from app.config import get_settings
from app.registry import handle_call_rpc

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_workbooks_list_live(monkeypatch: pytest.MonkeyPatch) -> None:
    api_host = os.getenv("DATALENS_API_BASE") or os.getenv("DATALENS_API_HOST")
    if not api_host or api_host == "http://datalens-api.example:8393":
        api_host = "http://127.0.0.1:8393"
    api_host = api_host.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            health = await client.get(f"{api_host}/health")
    except httpx.RequestError as exc:
        pytest.skip(f"DataLens API недоступен по {api_host}: {exc}")

    assert health.status_code == 200

    monkeypatch.setenv("DATALENS_API_HOST", api_host)
    get_settings.cache_clear()

    result = json.loads(
        await handle_call_rpc(
            "getWorkbooksList",
            {"page": 0, "pageSize": 5},
        )
    )

    assert result["http_status"] == 200
    assert "workbooks" in result["body"]
