from app.adapters.transfer import import_ids_to_cloud, import_status_to_cloud
from app.auth import AuthContext
from app.clients.meta_manager import get_meta_manager_client
from app.models.generated import (
    GetWorkbookImportStatusArgs,
    GetWorkbookImportStatusResult,
    StartWorkbookImportArgs,
    StartWorkbookImportResult,
)


async def start_workbook_import(
    args: StartWorkbookImportArgs, _ctx: AuthContext
) -> StartWorkbookImportResult:
    client = await get_meta_manager_client()
    raw = await client.request(
        "POST",
        "/workbooks/import",
        json=args.model_dump(by_alias=True, exclude_none=True, mode="json"),
    )
    return StartWorkbookImportResult.model_validate(
        import_ids_to_cloud(raw, what="start import")
    )


async def get_workbook_import_status(
    args: GetWorkbookImportStatusArgs, _ctx: AuthContext
) -> GetWorkbookImportStatusResult:
    client = await get_meta_manager_client()
    raw = await client.request("GET", f"/workbooks/import/{args.importId}")
    return GetWorkbookImportStatusResult.model_validate(import_status_to_cloud(raw))
