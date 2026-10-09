from app.client import call_rpc, list_rpc_paths
from app.results import tool_json

READ_TOOLS: dict[str, str] = {
    "get_workbooks_list": "getWorkbooksList",
    "get_workbook": "getWorkbook",
    "get_workbooks_by_ids": "getWorkbooksByIds",
    "get_workbook_entries": "getWorkbookEntries",
    "get_collection": "getCollection",
    "get_collections_by_ids": "getCollectionsByIds",
    "get_collection_content": "getCollectionContent",
    "get_collection_breadcrumbs": "getCollectionBreadcrumbs",
    "get_root_collection_permissions": "getRootCollectionPermissions",
    "get_entries": "getEntries",
    "list_directory": "listDirectory",
    "get_entries_relations": "getEntriesRelations",
    "get_entries_permissions": "getEntriesPermissions",
    "get_permissions": "getPermissions",
    "get_connection": "getConnection",
    "get_dataset": "getDataset",
    "validate_dataset": "validateDataset",
    "get_dashboard": "getDashboard",
    "get_wizard_chart": "getWizardChart",
    "get_ql_chart": "getQLChart",
    "get_workbook_export_status": "getWorkbookExportStatus",
    "get_workbook_export_result": "getWorkbookExportResult",
    "get_workbook_import_status": "getWorkbookImportStatus",
}

CREATE_TOOLS: dict[str, str] = {
    "create_dashboard": "createDashboard",
    "create_wizard_chart": "createWizardChart",
    "create_ql_chart": "createQLChart",
}

DATA_TOOLS: dict[str, str] = {
    "query_dataset": "queryDataset",
    "get_dataset_field_values": "getDatasetFieldValues",
    "get_chart_data": "getChartData",
}

DATA_TOOL_DESCRIPTIONS: dict[str, str] = {
    "query_dataset": (
        "Read-only aggregated query against a dataset. Args: datasetId; fields "
        "(1–30 field titles or ids; measures aggregate, dimensions group); "
        "calculatedFields [{title, formula}] (DataLens formula syntax, max 10); "
        "filters [{field, op, values}] with op one of eq, ne, gt, gte, lt, lte, "
        "in, nin, between, contains, icontains, startswith, isnull, isnotnull "
        "(isnull/isnotnull: no values; between: 2; in/nin: ≥1; others: 1); "
        "orderBy [{field, direction asc|desc}]; limit (default 100, max 500). "
        "Returns {columns[{title,dataType}], rows, rowCount, truncated}. "
        "Use get_dataset to discover available fields."
    ),
    "get_dataset_field_values": (
        "Distinct values or min/max for a dataset field. Args: datasetId, field; "
        "mode=distinct (optional case-insensitive search substring; limit default "
        "100, max 200) or mode=range (min/max); optional filters as in "
        "query_dataset. Returns {field, values, truncated} or {field, min, max}."
    ),
    "get_chart_data": (
        "Data for an existing chart as a uniform table. Args: chartId; params "
        "(dashboard/chart parameters as {name: value or [values]}). Returns "
        "{chartId, title, visualization, datasetIds, columns, rows, rowCount, "
        "truncated, normalized, note}. Tables, metrics, and line/area/column/bar "
        "charts are normalized (charts as long table x/series/value); other "
        "visualizations set normalized=false with a note — use query_dataset on "
        "datasetIds instead."
    ),
}


def _rpc_path_to_method(path: str) -> str:
    return path.removeprefix("/rpc/")


async def handle_list_rpc_methods() -> str:
    paths = await list_rpc_paths()
    methods = sorted(_rpc_path_to_method(path) for path in paths)
    return tool_json({"methods": methods})


async def handle_call_rpc(method: str, args: dict) -> str:
    http_status, body = await call_rpc(method, args)
    return tool_json({"http_status": http_status, "body": body})
