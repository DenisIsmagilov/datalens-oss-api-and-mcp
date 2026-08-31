import json

import httpx
import pytest
import respx

from app.registry import handle_call_rpc, handle_list_rpc_methods
from app.server import build_mcp


@pytest.mark.asyncio
@respx.mock
async def test_list_rpc_methods_filters_rpc_paths():
    respx.get("http://datalens-api.example:8393/json/").mock(
        return_value=httpx.Response(
            200, json={"paths": {"/rpc/getWorkbook": {}, "/health": {}}}
        )
    )
    text = await handle_list_rpc_methods()
    data = json.loads(text)
    assert data["methods"] == ["getWorkbook"]


@pytest.mark.asyncio
@respx.mock
async def test_call_rpc_posts_body():
    route = respx.post("http://datalens-api.example:8393/rpc/getWorkbook").mock(
        return_value=httpx.Response(200, json={"workbookId": "abc", "title": "T"})
    )
    text = await handle_call_rpc("getWorkbook", {"workbookId": "abc"})
    data = json.loads(text)
    assert data["http_status"] == 200
    assert data["body"]["title"] == "T"
    assert json.loads(route.calls[0].request.content) == {"workbookId": "abc"}


@pytest.mark.asyncio
async def test_build_mcp_registers_meta_tools():
    mcp = build_mcp()
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {"list_rpc_methods", "call_rpc"} <= names
