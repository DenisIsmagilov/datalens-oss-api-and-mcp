from typing import Any

from app.adapters.common import dump_model
from app.adapters.entries import (
    entries_permissions_item_to_cloud,
    relations_to_cloud,
    rename_result_to_cloud,
)
from app.auth import AuthContext
from app.clients.us import get_us_client, us_public_request
from app.errors import ApiError
from app.models.generated import (
    GetEntriesPermissionsArgs,
    GetEntriesPermissionsResult,
    GetEntriesRelationsArgs,
    GetEntriesRelationsResult,
    RenameEntryArgs,
    RenameEntryResult,
)


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


async def get_entries_relations(
    args: GetEntriesRelationsArgs, _ctx: AuthContext
) -> GetEntriesRelationsResult:
    raw = await _us_private(
        "POST",
        "/private/v1/get-entries-relations",
        json=dump_model(args),
    )
    return GetEntriesRelationsResult.model_validate(relations_to_cloud(raw))


async def rename_entry(args: RenameEntryArgs, _ctx: AuthContext) -> RenameEntryResult:
    payload = dump_model(args)
    entry_id = payload.pop("entryId")
    raw = await _us_private(
        "POST",
        f"/private/entries/{entry_id}/rename",
        json=payload,
    )
    return RenameEntryResult.model_validate(rename_result_to_cloud(raw))


async def get_entries_permissions(
    args: GetEntriesPermissionsArgs, _ctx: AuthContext
) -> GetEntriesPermissionsResult:
    payload = dump_model(args)
    result: dict[str, dict] = {}
    for entry_id in payload["entryIds"]:
        try:
            raw = await _us_public(
                "GET",
                f"/v1/entries/{entry_id}/access-description",
            )
        except ApiError as exc:
            if exc.status_code == 404:
                result[entry_id] = {"error": "NOT_FOUND"}
                continue
            raise
        result[entry_id] = entries_permissions_item_to_cloud(raw)
    return GetEntriesPermissionsResult.model_validate(result)
