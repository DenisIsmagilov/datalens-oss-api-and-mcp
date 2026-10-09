import json

import httpx
import pytest
import respx

from app.clients.datalens_api import DatalensApiClient
from app.packs import Pack, load_packs
from app.tools import build_registry
from app.tools.base import ToolContext, ToolError, run_tool
from app.tools.scope_cache import ScopeCache

API = "http://datalens-api.example:8393"


@pytest.fixture
async def api():
    client = DatalensApiClient(API, "dl-token", timeout_sec=5)
    yield client
    await client.aclose()


def _ctx(api, workbook_ids=("wb1",)) -> ToolContext:
    return ToolContext(api=api, pack=Pack(name="p", title="P", workbook_ids=list(workbook_ids)), scope=ScopeCache())


async def _run(name: str, args: dict, ctx: ToolContext) -> dict:
    return await run_tool(build_registry().get(name), args, ctx)


@respx.mock
async def test_list_entries_defaults_to_pack_workbook_and_fills_scope(api):
    route = respx.post(f"{API}/rpc/getWorkbookEntries").mock(
        return_value=httpx.Response(
            200,
            json={"entries": [{"entryId": "c1", "scope": "widget", "type": "graph_wizard_node", "key": "1/Чарт", "workbookId": "wb1"}]},
        )
    )
    ctx = _ctx(api)
    result = await _run("list_workbook_entries", {"scope": "widget"}, ctx)
    assert json.loads(route.calls[0].request.content) == {"workbookId": "wb1", "pageSize": 100, "scope": "widget"}
    assert result["entries"][0]["title"] == "Чарт"
    assert ctx.scope.get("c1") == "wb1"


@respx.mock
async def test_list_entries_outside_scope_is_rejected_without_call(api):
    with pytest.raises(ToolError) as exc:
        await _run("list_workbook_entries", {"workbookId": "other"}, _ctx(api))
    assert exc.value.code == "OUT_OF_SCOPE"


async def test_list_entries_without_default_workbook(api):
    with pytest.raises(ToolError) as exc:
        await _run("list_workbook_entries", {}, _ctx(api, workbook_ids=()))
    assert exc.value.code == "INVALID_ARGUMENT"


@respx.mock
async def test_get_chart_falls_back_to_ql(api):
    respx.post(f"{API}/rpc/getWizardChart").mock(
        return_value=httpx.Response(404, json={"code": "NOT_FOUND", "message": "no", "details": {}})
    )
    respx.post(f"{API}/rpc/getQLChart").mock(
        return_value=httpx.Response(
            200,
            json={"entryId": "q1", "key": "1/QL", "type": "table_ql_node", "workbookId": "wb1", "data": {"shared": json.dumps({"queryValue": "SELECT 1"})}},
        )
    )
    result = await _run("get_chart", {"chartId": "q1"}, _ctx(api))
    assert result["kind"] == "ql" and result["query"] == "SELECT 1"


@respx.mock
async def test_get_chart_outside_scope(api):
    respx.post(f"{API}/rpc/getWizardChart").mock(
        return_value=httpx.Response(200, json={"entryId": "c9", "type": "graph_wizard_node", "workbookId": "other", "data": {}})
    )
    with pytest.raises(ToolError) as exc:
        await _run("get_chart", {"chartId": "c9"}, _ctx(api))
    assert exc.value.code == "OUT_OF_SCOPE"
    assert exc.value.details["allowedWorkbookIds"] == ["wb1"]


@respx.mock
async def test_query_dataset_checks_scope_once_and_passes_args(api):
    lookup = respx.post(f"{API}/rpc/getDataset").mock(
        return_value=httpx.Response(200, json={"id": "ds1", "workbook_id": "wb1"})
    )
    query = respx.post(f"{API}/rpc/queryDataset").mock(
        return_value=httpx.Response(200, json={"columns": [], "rows": [], "rowCount": 0, "truncated": False})
    )
    ctx = _ctx(api)
    args = {"datasetId": "ds1", "fields": ["Город"], "filters": [{"field": "Город", "op": "in", "values": ["Москва"]}]}
    await _run("query_dataset", args, ctx)
    await _run("query_dataset", args, ctx)
    assert lookup.call_count == 1 and query.call_count == 2
    sent = json.loads(query.calls[0].request.content)
    assert sent["fields"] == ["Город"] and sent["limit"] == 100
    assert sent["filters"] == [{"field": "Город", "op": "in", "values": ["Москва"]}]


@respx.mock
async def test_query_dataset_outside_scope(api):
    respx.post(f"{API}/rpc/getDataset").mock(return_value=httpx.Response(200, json={"id": "ds2", "workbook_id": "other"}))
    query = respx.post(f"{API}/rpc/queryDataset")
    with pytest.raises(ToolError) as exc:
        await _run("query_dataset", {"datasetId": "ds2", "fields": ["a"]}, _ctx(api))
    assert exc.value.code == "OUT_OF_SCOPE" and query.call_count == 0


@respx.mock
async def test_query_dataset_without_scope_skips_lookup(api):
    respx.post(f"{API}/rpc/queryDataset").mock(
        return_value=httpx.Response(200, json={"columns": [], "rows": [[1]], "rowCount": 1, "truncated": False})
    )
    result = await _run("query_dataset", {"datasetId": "ds1", "fields": ["a"]}, _ctx(api, workbook_ids=()))
    assert result["rowCount"] == 1


@respx.mock
async def test_api_error_becomes_tool_error(api):
    respx.post(f"{API}/rpc/queryDataset").mock(
        return_value=httpx.Response(400, json={"code": "INVALID_ARGUMENT", "message": "Unknown field", "details": {"availableFields": ["A"]}})
    )
    with pytest.raises(ToolError) as exc:
        await _run("query_dataset", {"datasetId": "ds1", "fields": ["x"]}, _ctx(api, workbook_ids=()))
    assert exc.value.code == "INVALID_ARGUMENT" and exc.value.details == {"availableFields": ["A"]}


async def test_invalid_args_are_reported_without_input(api):
    with pytest.raises(ToolError) as exc:
        await _run("query_dataset", {"datasetId": "ds1", "fields": [], "secret": "значение"}, _ctx(api))
    assert exc.value.code == "INVALID_ARGUMENT"
    assert all(set(error) == {"loc", "msg", "type"} for error in exc.value.details["errors"])
    assert "значение" not in json.dumps(exc.value.details, ensure_ascii=False)


@respx.mock
async def test_get_chart_data_hint_for_unnormalized(api):
    respx.post(f"{API}/rpc/getWizardChart").mock(
        return_value=httpx.Response(200, json={"entryId": "c1", "type": "d3_wizard_node", "workbookId": "wb1", "data": {}})
    )
    route = respx.post(f"{API}/rpc/getChartData").mock(
        return_value=httpx.Response(200, json={"chartId": "c1", "normalized": False, "datasetIds": ["ds1"], "rows": [], "note": "n"})
    )
    result = await _run("get_chart_data", {"chartId": "c1", "params": {"Город": ["Москва"]}}, _ctx(api))
    assert "query_dataset" in result["hint"]
    assert json.loads(route.calls[0].request.content) == {"chartId": "c1", "params": {"Город": ["Москва"]}}


async def test_semantic_tools_on_bundled_pack(api):
    pack = load_packs("/app/packs").get("demo")
    ctx = ToolContext(api=api, pack=pack, scope=ScopeCache())
    found = await _run("semantic_search", {"query": "продажи на маркетплейсах"}, ctx)
    assert "demo_sales" in [i["id"] for i in found["intents"]]
    intent = await _run("get_intent", {"intentId": "demo_sales"}, ctx)
    assert intent["dataset_id"] == "ds-demo"
    with pytest.raises(ToolError) as exc:
        await _run("get_intent", {"intentId": "nope"}, ctx)
    assert exc.value.code == "NOT_FOUND" and exc.value.details["availableIntents"] == ["demo_sales"]


def test_scope_cache_expires():
    now = [0.0]
    cache = ScopeCache(ttl_sec=10, clock=lambda: now[0])
    cache.put("e1", "wb1")
    cache.put("e2", None)
    assert cache.get("e1") == "wb1" and cache.get("e2") == ""
    now[0] = 11
    assert cache.get("e1") is None
