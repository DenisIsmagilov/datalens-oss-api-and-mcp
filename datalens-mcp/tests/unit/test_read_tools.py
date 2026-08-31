import json

import httpx
import pytest
import respx

from app.registry import READ_TOOLS, handle_call_rpc
from app.server import build_mcp


def test_read_tools_table_complete():
    assert "get_workbooks_list" in READ_TOOLS
    assert READ_TOOLS["get_wizard_chart"] == "getWizardChart"
    assert len(READ_TOOLS) == 23


@pytest.mark.asyncio
@respx.mock
async def test_get_workbook_shortcut_calls_rpc():
    respx.post("http://datalens-api.example:8393/rpc/getWorkbook").mock(
        return_value=httpx.Response(200, json={"workbookId": "w1", "title": "X"})
    )
    text = await handle_call_rpc("getWorkbook", {"workbookId": "w1"})
    assert json.loads(text)["body"]["title"] == "X"


@pytest.mark.asyncio
async def test_build_mcp_lists_all_read_tools():
    mcp = build_mcp()
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert READ_TOOLS.keys() <= names
