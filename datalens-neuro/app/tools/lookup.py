from typing import Literal

from app.clients.datalens_api import DatalensApiClient, DatalensApiError
from app.packs import Pack
from app.tools.base import ToolContext, ToolError

_FALLBACK_STATUSES = {400, 404}
_CHART_METHODS = {"wizard": "getWizardChart", "ql": "getQLChart"}


def chart_kind(body: dict) -> str:
    return "ql" if str(body.get("type") or "").endswith("_ql_node") else "wizard"


async def load_chart(api: DatalensApiClient, chart_id: str, kind: str = "auto") -> tuple[str, dict]:
    order = ["wizard", "ql"] if kind == "auto" else [kind]
    last_error: DatalensApiError | None = None
    for candidate in order:
        try:
            body = await api.rpc(_CHART_METHODS[candidate], {"chartId": chart_id})
        except DatalensApiError as exc:
            if exc.status_code not in _FALLBACK_STATUSES:
                raise
            last_error = exc
            continue
        return chart_kind(body), body
    assert last_error is not None
    raise last_error


def check_scope(pack: Pack, workbook_id: str | None, entry_id: str) -> None:
    if not pack.in_scope(workbook_id):
        raise ToolError(
            "OUT_OF_SCOPE",
            f"{entry_id} is outside the workbooks of this pack",
            {"entryId": entry_id, "workbookId": workbook_id, "allowedWorkbookIds": pack.workbook_ids},
        )


async def ensure_in_scope(ctx: ToolContext, entry_id: str, kind: Literal["dataset", "chart"]) -> None:
    if not ctx.pack.workbook_ids:
        return
    workbook_id = ctx.scope.get(entry_id)
    if workbook_id is None:
        if kind == "dataset":
            body = await ctx.api.rpc("getDataset", {"datasetId": entry_id})
            workbook_id = str(body.get("workbook_id") or "")
        else:
            _, body = await load_chart(ctx.api, entry_id)
            workbook_id = str(body.get("workbookId") or "")
        ctx.scope.put(entry_id, workbook_id)
    check_scope(ctx.pack, workbook_id, entry_id)
