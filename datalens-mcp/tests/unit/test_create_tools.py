import json

import httpx
import pytest
import respx

from app.registry import CREATE_TOOLS, handle_call_rpc
from app.server import build_mcp


def test_create_tools_table_complete():
    assert CREATE_TOOLS["create_dashboard"] == "createDashboard"
    assert CREATE_TOOLS["create_wizard_chart"] == "createWizardChart"
    assert CREATE_TOOLS["create_ql_chart"] == "createQLChart"
    assert len(CREATE_TOOLS) == 3


@pytest.mark.asyncio
@respx.mock
async def test_create_dashboard_shortcut_calls_rpc():
    route = respx.post("http://datalens-api.example:8393/rpc/createDashboard").mock(
        return_value=httpx.Response(200, json={"entryId": "dash1", "title": "New"})
    )
    args = {"workbookId": "w1", "title": "New", "data": {"schemeVersion": 8}}
    text = await handle_call_rpc("createDashboard", args)
    data = json.loads(text)
    assert data["http_status"] == 200
    assert data["body"]["entryId"] == "dash1"
    assert json.loads(route.calls[0].request.content) == args


@pytest.mark.asyncio
async def test_build_mcp_lists_all_create_tools():
    mcp = build_mcp()
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert CREATE_TOOLS.keys() <= names


def test_no_delete_shortcuts():
    names = {t.name for t in build_mcp()._tool_manager.list_tools()}
    assert "delete_dashboard" not in names
    assert "update_dashboard" not in names
    assert "delete_wizard_chart" not in names
    assert "create_dashboard" in names
    assert "create_wizard_chart" in names
    assert "create_ql_chart" in names
