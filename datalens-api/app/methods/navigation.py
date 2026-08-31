from typing import Any

from app.adapters.common import dump_model
from app.adapters.entries import (
    flatten_query,
    get_entries_v2_to_cloud,
    list_directory_to_cloud,
)
from app.auth import AuthContext
from app.clients.us import get_us_client
from app.models.generated import (
    GetEntriesV2Args,
    GetEntriesV2Result,
    ListDirectoryArgs,
    ListDirectoryResult,
)


async def _us_private(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: Any = None,
) -> Any:
    return await get_us_client().request(method, path, params=params, json=json)


async def get_entries(args: GetEntriesV2Args, _ctx: AuthContext) -> GetEntriesV2Result:
    raw = await _us_private(
        "POST",
        "/private/v1/get-entries",
        json=dump_model(args),
    )
    return GetEntriesV2Result.model_validate(get_entries_v2_to_cloud(raw))


async def list_directory(
    args: ListDirectoryArgs, _ctx: AuthContext
) -> ListDirectoryResult:
    raw = await _us_private(
        "GET",
        "/private/entries",
        params=flatten_query(dump_model(args)),
    )
    return ListDirectoryResult.model_validate(list_directory_to_cloud(raw))
