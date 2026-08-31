from app.adapters.transfer import (
    export_id_to_cloud,
    export_result_to_cloud,
    export_status_to_cloud,
)
from app.auth import AuthContext
from app.clients.meta_manager import get_meta_manager_client
from app.errors import ApiError
from app.models.generated import (
    CancelWorkbookExportArgs,
    CancelWorkbookExportResult,
    GetWorkbookExportResultArgs,
    GetWorkbookExportResultResult,
    GetWorkbookExportStatusArgs,
    GetWorkbookExportStatusResult,
    StartWorkbookExportArgs,
    StartWorkbookExportResult,
)

_NOT_COMPLETED = "WORKBOOK_EXPORT_NOT_COMPLETED"


def _is_export_not_completed(exc: ApiError) -> bool:
    haystack = " ".join(
        [
            str(exc.code),
            str(exc.message),
            str(exc.details),
        ]
    )
    return _NOT_COMPLETED in haystack


async def start_workbook_export(
    args: StartWorkbookExportArgs, _ctx: AuthContext
) -> StartWorkbookExportResult:
    client = await get_meta_manager_client()
    raw = await client.request(
        "POST",
        "/workbooks/export",
        json={"workbookId": args.workbookId},
    )
    return StartWorkbookExportResult.model_validate(
        export_id_to_cloud(raw, what="start export")
    )


async def get_workbook_export_status(
    args: GetWorkbookExportStatusArgs, _ctx: AuthContext
) -> GetWorkbookExportStatusResult:
    client = await get_meta_manager_client()
    raw = await client.request("GET", f"/workbooks/export/{args.exportId}")
    return GetWorkbookExportStatusResult.model_validate(export_status_to_cloud(raw))


async def get_workbook_export_result(
    args: GetWorkbookExportResultArgs, _ctx: AuthContext
) -> GetWorkbookExportResultResult:
    client = await get_meta_manager_client()
    try:
        raw = await client.request("GET", f"/workbooks/export/{args.exportId}/result")
    except ApiError as exc:
        if exc.status_code == 409 and _is_export_not_completed(exc):
            raise ApiError(
                400,
                "INVALID_ARGUMENT",
                exc.message,
                details=exc.details,
            ) from exc
        raise
    return GetWorkbookExportResultResult.model_validate(export_result_to_cloud(raw))


async def cancel_workbook_export(
    args: CancelWorkbookExportArgs, _ctx: AuthContext
) -> CancelWorkbookExportResult:
    client = await get_meta_manager_client()
    raw = await client.request("POST", f"/workbooks/export/{args.exportId}/cancel")
    return CancelWorkbookExportResult.model_validate(
        export_id_to_cloud(raw, what="cancel export")
    )
