import json

import httpx
import pytest
import respx

from app.client import _get_client
from app.config import get_settings
from app.registry import DATA_TOOL_DESCRIPTIONS, DATA_TOOLS, handle_call_rpc
from app.server import build_mcp


def test_data_tools_table():
    assert DATA_TOOLS == {
        "query_dataset": "queryDataset",
        "get_dataset_field_values": "getDatasetFieldValues",
        "get_chart_data": "getChartData",
    }


@pytest.mark.asyncio
@respx.mock
async def test_query_dataset_args_pass_through():
    route = respx.post("http://datalens-api.example:8393/rpc/queryDataset").mock(
        return_value=httpx.Response(
            200, json={"columns": [], "rows": [], "rowCount": 0, "truncated": False}
        )
    )
    args = {
        "datasetId": "ds1",
        "fields": ["Город"],
        "filters": [{"field": "Город", "op": "in", "values": ["Москва"]}],
    }
    data = json.loads(await handle_call_rpc("queryDataset", args))
    assert data["http_status"] == 200
    assert json.loads(route.calls[0].request.content) == args


@pytest.mark.asyncio
async def test_build_mcp_has_31_tools():
    tools = await build_mcp().list_tools()
    names = {tool.name for tool in tools}
    assert DATA_TOOLS.keys() <= names
    assert len(tools) == 31


@pytest.mark.asyncio
async def test_data_tool_descriptions_match_registry():
    tools_by_name = {tool.name: tool for tool in await build_mcp().list_tools()}
    assert set(DATA_TOOL_DESCRIPTIONS.keys()) == set(DATA_TOOLS.keys())
    for tool_name, expected in DATA_TOOL_DESCRIPTIONS.items():
        assert expected.strip(), f"{tool_name} has empty description"
        assert tools_by_name[tool_name].description == expected


def test_client_timeout_from_settings(monkeypatch):
    import app.client as client_module

    monkeypatch.setenv("DATALENS_API_TIMEOUT_SEC", "123")
    get_settings.cache_clear()
    monkeypatch.setattr(client_module, "_client", None)
    assert _get_client().timeout.read == 123
    monkeypatch.setattr(client_module, "_client", None)
    get_settings.cache_clear()
