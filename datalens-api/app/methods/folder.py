from typing import Any

from pydantic import BaseModel

from app.adapters.common import dump_model
from app.adapters.entries import (
    create_folder_to_cloud,
    get_permissions_to_cloud,
    move_result_to_cloud,
)
from app.auth import AuthContext
from app.clients.us import get_us_client, us_public_request
from app.models.generated import (
    CreateFolderArgs,
    CreateFolderResult,
    DeleteFolderArgs,
    GetPermissionsArgs,
    GetPermissionsResult,
    MoveEntryArgs,
    MoveEntryResult,
)


class DeleteFolderResult(BaseModel):
    pass


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


async def create_folder(args: CreateFolderArgs, _ctx: AuthContext) -> CreateFolderResult:
    payload = dump_model(args)
    payload["scope"] = "folder"
    raw = await _us_private("POST", "/private/entries", json=payload)
    return CreateFolderResult.model_validate(create_folder_to_cloud(raw))


async def delete_folder(args: DeleteFolderArgs, _ctx: AuthContext) -> DeleteFolderResult:
    folder_id = dump_model(args)["folderId"]
    await _us_private("DELETE", f"/private/entries/{folder_id}")
    return DeleteFolderResult()


async def move_folder_entry(args: MoveEntryArgs, _ctx: AuthContext) -> MoveEntryResult:
    payload = dump_model(args)
    entry_id = payload.pop("entryId")
    raw = await _us_private(
        "POST",
        f"/private/entries/{entry_id}",
        json=payload,
    )
    return MoveEntryResult.model_validate(move_result_to_cloud(raw))


async def get_permissions(
    args: GetPermissionsArgs, _ctx: AuthContext
) -> GetPermissionsResult:
    entry_id = dump_model(args)["entryId"]
    raw = await _us_public("GET", f"/v1/entries/{entry_id}/access-description")
    return GetPermissionsResult.model_validate(get_permissions_to_cloud(raw))
