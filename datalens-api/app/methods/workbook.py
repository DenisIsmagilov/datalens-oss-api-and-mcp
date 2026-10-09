from typing import Any

from pydantic import BaseModel

from app.adapters.common import dump_model
from app.adapters.workbook import (
    create_workbook_to_cloud,
    entries_page_to_cloud,
    workbook_to_cloud,
    workbooks_bulk_to_cloud,
    workbooks_from_us,
    workbooks_page_to_cloud,
)
from app.auth import AuthContext
from app.clients.us import get_us_client, us_public_request
from app.models.generated import (
    CreateWorkbookArgs,
    CreateWorkbookResult,
    DeleteWorkbookArgs,
    DeleteWorkbooksArgs,
    GetWorkbookArgs,
    GetWorkbookEntriesArgs,
    GetWorkbookEntriesResult,
    GetWorkbookResult,
    GetWorkbooksByIdsArgs,
    GetWorkbooksListArgs,
    GetWorkbooksListResult,
    MoveWorkbookArgs,
    MoveWorkbooksArgs,
    UpdateWorkbookArgs,
    Workbook,
)


class WorkbooksBulkResult(BaseModel):
    workbooks: list[Workbook]


def _us_list_params(payload: dict) -> dict:
    params = dict(payload)
    for key in ("page", "pageSize"):
        value = params.get(key)
        if value is not None:
            params[key] = int(value)
    return params


def _flatten_query(payload: dict, *, drop: set[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key, value in payload.items():
        if key in drop or value is None:
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_value is not None:
                    params[f"{key}[{sub_key}]"] = sub_value
        else:
            params[key] = value
    return _us_list_params(params)


async def _us_private(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: Any = None,
) -> Any:
    return await get_us_client().request(method, path, params=params, json=json)


async def _us_public(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: Any = None,
) -> Any:
    return await us_public_request(method, path, params=params, json=json)


async def get_workbooks_list(
    args: GetWorkbooksListArgs, _ctx: AuthContext
) -> GetWorkbooksListResult:
    payload = dump_model(args)
    include_permissions = bool(payload.get("includePermissionsInfo"))
    raw = await _us_public(
        "GET",
        "/v2/workbooks",
        params=_us_list_params(payload),
    )
    return GetWorkbooksListResult.model_validate(
        workbooks_page_to_cloud(raw, include_permissions=include_permissions)
    )


async def create_workbook(
    args: CreateWorkbookArgs, _ctx: AuthContext
) -> CreateWorkbookResult:
    raw = await _us_private("POST", "/private/v2/workbooks", json=dump_model(args))
    return CreateWorkbookResult.model_validate(create_workbook_to_cloud(raw))


async def get_workbook(args: GetWorkbookArgs, _ctx: AuthContext) -> GetWorkbookResult:
    payload = dump_model(args)
    workbook_id = payload.pop("workbookId")
    raw = await _us_private(
        "GET",
        f"/private/v2/workbooks/{workbook_id}",
        params=payload,
    )
    return GetWorkbookResult.model_validate(
        workbook_to_cloud(raw, include_permissions=True)
    )


async def update_workbook(args: UpdateWorkbookArgs, _ctx: AuthContext) -> Workbook:
    payload = dump_model(args)
    workbook_id = payload.pop("workbookId")
    raw = await _us_private(
        "POST",
        f"/private/v2/workbooks/{workbook_id}/update",
        json=payload,
    )
    return Workbook.model_validate(workbook_to_cloud(raw))


def _minimal_workbook_raw(workbook_id: str) -> dict:
    return {"workbookId": workbook_id, "title": ""}


def _ensure_delete_workbook_raw(raw: dict, workbook_id: str) -> dict:
    if raw.get("workbookId"):
        return raw
    return _minimal_workbook_raw(workbook_id)


def _ensure_delete_workbooks_raw(raw: dict | list, workbook_ids: list[str]) -> dict | list:
    if isinstance(raw, list):
        if raw:
            return raw
    elif raw.get("workbooks"):
        return raw
    return {"workbooks": [_minimal_workbook_raw(workbook_id) for workbook_id in workbook_ids]}


async def delete_workbook(args: DeleteWorkbookArgs, _ctx: AuthContext) -> Workbook:
    payload = dump_model(args)
    workbook_id = payload["workbookId"]
    raw = await _us_private(
        "DELETE",
        f"/private/v2/workbooks/{workbook_id}",
    )
    return Workbook.model_validate(
        workbook_to_cloud(_ensure_delete_workbook_raw(raw, workbook_id))
    )


async def delete_workbooks(
    args: DeleteWorkbooksArgs, _ctx: AuthContext
) -> WorkbooksBulkResult:
    payload = dump_model(args)
    raw = await _us_public(
        "DELETE",
        "/v2/delete-workbooks",
        json=payload,
    )
    return WorkbooksBulkResult.model_validate(
        workbooks_bulk_to_cloud(
            _ensure_delete_workbooks_raw(raw, payload["workbookIds"])
        )
    )


async def move_workbook(args: MoveWorkbookArgs, _ctx: AuthContext) -> Workbook:
    payload = args.model_dump(by_alias=True, mode="json")
    workbook_id = payload.pop("workbookId")
    raw = await _us_public(
        "POST",
        f"/v2/workbooks/{workbook_id}/move",
        json=payload,
    )
    return Workbook.model_validate(workbook_to_cloud(raw))


async def move_workbooks(
    args: MoveWorkbooksArgs, _ctx: AuthContext
) -> WorkbooksBulkResult:
    payload = args.model_dump(by_alias=True, mode="json")
    raw = await _us_public("POST", "/v2/move-workbooks", json=payload)
    return WorkbooksBulkResult.model_validate(workbooks_bulk_to_cloud(raw))


async def get_workbooks_by_ids(
    args: GetWorkbooksByIdsArgs, _ctx: AuthContext
) -> list[Workbook]:
    raw = await _us_public(
        "POST",
        "/v2/workbooks-get-list-by-ids",
        json=dump_model(args),
    )
    return [Workbook.model_validate(item) for item in workbooks_from_us(raw)]


async def get_workbook_entries(
    args: GetWorkbookEntriesArgs, _ctx: AuthContext
) -> GetWorkbookEntriesResult:
    payload = dump_model(args)
    workbook_id = payload.pop("workbookId")
    raw = await _us_private(
        "GET",
        f"/private/v2/workbooks/{workbook_id}/entries",
        params=_flatten_query(payload, drop=set()),
    )
    return GetWorkbookEntriesResult.model_validate(entries_page_to_cloud(raw))
