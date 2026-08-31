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


def _rpc_path_to_method(path: str) -> str:
    return path.removeprefix("/rpc/")


async def handle_list_rpc_methods() -> str:
    paths = await list_rpc_paths()
    methods = sorted(_rpc_path_to_method(path) for path in paths)
    return tool_json({"methods": methods})


async def handle_call_rpc(method: str, args: dict) -> str:
    http_status, body = await call_rpc(method, args)
    return tool_json({"http_status": http_status, "body": body})
