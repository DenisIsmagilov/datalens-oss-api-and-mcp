from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.tools.base import Tool, ToolContext, ToolError
from app.tools.compact import compact_chart, compact_dashboard, compact_dataset, compact_entries
from app.tools.lookup import check_scope, ensure_in_scope, load_chart

EntryId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Scalar = str | int | float | bool
FilterOp = Literal[
    "eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "between",
    "contains", "icontains", "startswith", "isnull", "isnotnull",
]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListWorkbookEntriesArgs(_Args):
    workbookId: EntryId | None = Field(None, description="Workbook id; defaults to the first workbook of the pack")
    scope: Literal["dash", "widget", "dataset", "connection"] | None = Field(
        None, description="dash = dashboards, widget = charts, dataset = datasets"
    )
    page: int | None = Field(None, ge=0)
    pageSize: int = Field(100, ge=1, le=200)


class GetDashboardArgs(_Args):
    dashboardId: EntryId


class GetChartArgs(_Args):
    chartId: EntryId
    kind: Literal["auto", "wizard", "ql"] = "auto"


class GetDatasetArgs(_Args):
    datasetId: EntryId


class DataFilter(_Args):
    field: str = Field(min_length=1, description="Field title or guid")
    op: FilterOp
    values: list[Scalar] = Field(default_factory=list, max_length=1000)


class CalculatedField(_Args):
    title: str = Field(min_length=1, max_length=200)
    formula: str = Field(min_length=1, max_length=5000, description="DataLens formula, e.g. SUM([Sales]) / COUNTD([Order])")


class OrderBy(_Args):
    field: str = Field(min_length=1)
    direction: Literal["asc", "desc"] = "asc"


class QueryDatasetArgs(_Args):
    datasetId: EntryId
    fields: list[str] = Field(min_length=1, max_length=30, description="Field titles or guids, including calculatedFields titles")
    calculatedFields: list[CalculatedField] = Field(default_factory=list, max_length=10)
    filters: list[DataFilter] = Field(default_factory=list, max_length=20)
    orderBy: list[OrderBy] = Field(default_factory=list, max_length=10)
    limit: int = Field(100, ge=1, le=500)


class GetDatasetFieldValuesArgs(_Args):
    datasetId: EntryId
    field: str = Field(min_length=1)
    mode: Literal["distinct", "range"] = "distinct"
    search: str | None = Field(None, max_length=200, description="Case-insensitive substring for mode=distinct")
    filters: list[DataFilter] = Field(default_factory=list, max_length=20)
    limit: int = Field(100, ge=1, le=200)


class GetChartDataArgs(_Args):
    chartId: EntryId
    params: dict[str, str | list[str]] = Field(
        default_factory=dict, description="Dashboard/chart parameters {name: value or [values]}"
    )


async def _list_entries(args: ListWorkbookEntriesArgs, ctx: ToolContext) -> dict:
    workbook_id = args.workbookId or (ctx.pack.workbook_ids[0] if ctx.pack.workbook_ids else None)
    if not workbook_id:
        raise ToolError("INVALID_ARGUMENT", "workbookId is required: the pack has no default workbook")
    check_scope(ctx.pack, workbook_id, workbook_id)
    payload: dict = {"workbookId": workbook_id, "pageSize": args.pageSize}
    if args.scope:
        payload["scope"] = args.scope
    if args.page is not None:
        payload["page"] = args.page
    body = await ctx.api.rpc("getWorkbookEntries", payload)
    for entry in body.get("entries") or []:
        if isinstance(entry, dict) and entry.get("entryId"):
            ctx.scope.put(str(entry["entryId"]), entry.get("workbookId") or workbook_id)
    return compact_entries(body)


async def _get_dashboard(args: GetDashboardArgs, ctx: ToolContext) -> dict:
    body = await ctx.api.rpc("getDashboard", {"dashboardId": args.dashboardId})
    entry = body.get("entry") if isinstance(body.get("entry"), dict) else {}
    workbook_id = entry.get("workbookId")
    ctx.scope.put(args.dashboardId, workbook_id)
    check_scope(ctx.pack, workbook_id, args.dashboardId)
    return compact_dashboard(body)


async def _get_chart(args: GetChartArgs, ctx: ToolContext) -> dict:
    kind, body = await load_chart(ctx.api, args.chartId, args.kind)
    workbook_id = body.get("workbookId")
    ctx.scope.put(args.chartId, workbook_id)
    check_scope(ctx.pack, workbook_id, args.chartId)
    return compact_chart(body, kind)


async def _get_dataset(args: GetDatasetArgs, ctx: ToolContext) -> dict:
    body = await ctx.api.rpc("getDataset", {"datasetId": args.datasetId})
    workbook_id = body.get("workbook_id")
    ctx.scope.put(args.datasetId, workbook_id)
    check_scope(ctx.pack, workbook_id, args.datasetId)
    return compact_dataset(body)


async def _query_dataset(args: QueryDatasetArgs, ctx: ToolContext) -> dict:
    await ensure_in_scope(ctx, args.datasetId, "dataset")
    return await ctx.api.rpc("queryDataset", args.model_dump(exclude_none=True))


async def _field_values(args: GetDatasetFieldValuesArgs, ctx: ToolContext) -> dict:
    await ensure_in_scope(ctx, args.datasetId, "dataset")
    return await ctx.api.rpc("getDatasetFieldValues", args.model_dump(exclude_none=True))


async def _chart_data(args: GetChartDataArgs, ctx: ToolContext) -> dict:
    await ensure_in_scope(ctx, args.chartId, "chart")
    result = await ctx.api.rpc("getChartData", args.model_dump())
    if result.get("normalized") is False:
        result["hint"] = "This visualization is not normalized: call query_dataset on datasetIds"
    return result


DATALENS_TOOLS = [
    Tool(
        "list_workbook_entries",
        "List dashboards (scope=dash), charts (scope=widget) and datasets (scope=dataset) of a workbook "
        "with ids and titles. workbookId defaults to the pack workbook. Start here to find entities by name.",
        ListWorkbookEntriesArgs,
        _list_entries,
    ),
    Tool(
        "get_dashboard",
        "Dashboard structure: tabs, charts on each tab (title, chartId, params) and selectors "
        "(title, params, datasetId, fieldId). Use it to see which charts answer the question.",
        GetDashboardArgs,
        _get_dashboard,
        source_type="dashboard",
        source_arg="dashboardId",
    ),
    Tool(
        "get_chart",
        "Chart config summary: kind (wizard or ql), visualization, datasetIds, fields by placeholder, "
        "filters; for QL charts the SQL query. Use it to learn which dataset and fields a chart uses.",
        GetChartArgs,
        _get_chart,
        source_type="chart",
        source_arg="chartId",
    ),
    Tool(
        "get_dataset",
        "Dataset fields: title, guid, type (DIMENSION or MEASURE), dataType, aggregation, description. "
        "Call it before query_dataset to pick exact field titles.",
        GetDatasetArgs,
        _get_dataset,
        source_type="dataset",
        source_arg="datasetId",
    ),
    Tool(
        "query_dataset",
        "Read-only aggregated query to a dataset. fields: 1-30 field titles or guids (measures are "
        "aggregated, dimensions group rows). calculatedFields: temporary formulas [{title, formula}] in "
        "DataLens syntax. filters: [{field, op, values}]; isnull/isnotnull take no values, between takes 2, "
        "in/nin take 1 or more, others take 1. orderBy: [{field, direction}]. limit default 100, max 500. "
        "Returns columns, rows, rowCount, truncated.",
        QueryDatasetArgs,
        _query_dataset,
        source_type="dataset",
        source_arg="datasetId",
    ),
    Tool(
        "get_dataset_field_values",
        "Distinct values of a field (mode=distinct, optional case-insensitive search substring, limit "
        "max 200) or its min/max (mode=range). Use it to find exact filter values and the date range.",
        GetDatasetFieldValuesArgs,
        _field_values,
        source_type="dataset",
        source_arg="datasetId",
    ),
    Tool(
        "get_chart_data",
        "Data of an existing chart as on screen, as a uniform table. params: dashboard/chart parameters "
        "{name: value or [values]}. Tables, metrics and line/area/column/bar charts are normalized "
        "(graphs as a long table x/series/value). If normalized=false, use query_dataset on datasetIds.",
        GetChartDataArgs,
        _chart_data,
        source_type="chart",
        source_arg="chartId",
    ),
]
