from typing import Any

from app.adapters.common import dump_model
from app.adapters.dashboard import dashboard_result
from app.auth import AuthContext
from app.clients.us import get_us_client
from app.us_entries import create_and_publish_entry
from app.models.generated import (
    CreateDashboardV1Args,
    DeleteDashboardArgs,
    GetDashboardV1Args,
    GetDashboardV1Result,
    UpdateDashboardV1Args,
)
from app.models.rpc_bi import EmptyResult


async def _us_private(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: Any = None,
) -> Any:
    return await get_us_client().request(method, path, params=params, json=json)


def _create_us_payload(entry: dict) -> dict:
    payload: dict[str, Any] = {
        "scope": "dash",
        "type": "",
        "data": entry["data"],
    }
    for key in ("workbookId", "name", "key", "meta"):
        if key in entry:
            payload[key] = entry[key]
    return payload


def _get_us_params(payload: dict) -> dict[str, Any]:
    params: dict[str, Any] = {}
    mapping = {
        "includePermissions": "includePermissionsInfo",
        "includeLinks": "includeLinks",
        "includeFavorite": "includeFavorite",
        "revId": "revId",
        "branch": "branch",
    }
    for src, dest in mapping.items():
        if src in payload:
            params[dest] = payload[src]
    return params


def _update_us_payload(payload: dict) -> dict:
    entry = payload["entry"]
    body: dict[str, Any] = {
        "mode": payload["mode"],
        "data": entry["data"],
    }
    if "meta" in entry:
        body["meta"] = entry["meta"]
    if payload.get("lockToken") is not None:
        body["lockToken"] = payload["lockToken"]
    return body


async def create_dashboard(
    args: CreateDashboardV1Args, _ctx: AuthContext
) -> GetDashboardV1Result:
    entry = dump_model(args)["entry"]
    raw = await create_and_publish_entry(_create_us_payload(entry))
    return GetDashboardV1Result.model_validate(dashboard_result(raw))


async def get_dashboard(
    args: GetDashboardV1Args, _ctx: AuthContext
) -> GetDashboardV1Result:
    payload = dump_model(args)
    dashboard_id = payload.pop("dashboardId")
    raw = await _us_private(
        "GET",
        f"/private/entries/{dashboard_id}",
        params=_get_us_params(payload),
    )
    return GetDashboardV1Result.model_validate(dashboard_result(raw))


async def update_dashboard(
    args: UpdateDashboardV1Args, _ctx: AuthContext
) -> GetDashboardV1Result:
    payload = dump_model(args)
    entry_id = payload["entry"]["entryId"]
    raw = await _us_private(
        "POST",
        f"/private/entries/{entry_id}",
        json=_update_us_payload(payload),
    )
    return GetDashboardV1Result.model_validate(dashboard_result(raw))


async def delete_dashboard(
    args: DeleteDashboardArgs, _ctx: AuthContext
) -> EmptyResult:
    payload = dump_model(args)
    dashboard_id = payload["dashboardId"]
    params = {}
    if payload.get("lockToken") is not None:
        params["lockToken"] = payload["lockToken"]
    await _us_private(
        "DELETE",
        f"/private/entries/{dashboard_id}",
        params=params or None,
    )
    return EmptyResult()
