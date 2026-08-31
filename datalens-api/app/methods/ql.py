from typing import Any

from app.adapters.chart import entry_to_chart
from app.adapters.common import dump_model
from app.auth import AuthContext
from app.clients.us import get_us_client
from app.models.generated import (
    CreateQLChartArgs,
    DeleteQLChartArgs,
    GetQLChartArgs,
    UpdateQLChartArgs,
)
from app.models.rpc_bi import ChartResult, EmptyResult

_QL_TYPE = "ql"


async def _us_private(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: Any = None,
) -> Any:
    return await get_us_client().request(method, path, params=params, json=json)


def _location_payload(payload: dict) -> dict[str, Any]:
    body: dict[str, Any] = {
        "scope": "widget",
        "type": _QL_TYPE,
        "data": payload["data"],
    }
    for key in ("workbookId", "name", "key", "meta", "annotation"):
        if key in payload:
            body[key] = payload[key]
    return body


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


async def create_ql_chart(args: CreateQLChartArgs, _ctx: AuthContext) -> ChartResult:
    raw = await _us_private(
        "POST", "/private/entries", json=_location_payload(dump_model(args))
    )
    return ChartResult.model_validate(entry_to_chart(raw))


async def get_ql_chart(args: GetQLChartArgs, _ctx: AuthContext) -> ChartResult:
    payload = dump_model(args)
    chart_id = payload.pop("chartId")
    raw = await _us_private(
        "GET",
        f"/private/entries/{chart_id}",
        params=_get_us_params(payload),
    )
    return ChartResult.model_validate(entry_to_chart(raw))


async def update_ql_chart(args: UpdateQLChartArgs, _ctx: AuthContext) -> ChartResult:
    payload = dump_model(args)
    entry_id = payload["entryId"]
    body: dict[str, Any] = {
        "mode": payload["mode"],
        "data": payload["data"],
    }
    if "annotation" in payload:
        body["annotation"] = payload["annotation"]
    raw = await _us_private("POST", f"/private/entries/{entry_id}", json=body)
    return ChartResult.model_validate(entry_to_chart(raw))


async def delete_ql_chart(args: DeleteQLChartArgs, _ctx: AuthContext) -> EmptyResult:
    chart_id = dump_model(args)["chartId"]
    await _us_private("DELETE", f"/private/entries/{chart_id}")
    return EmptyResult()
