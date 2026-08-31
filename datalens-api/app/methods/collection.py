from typing import Any

from pydantic import BaseModel

from app.adapters.collection import (
    breadcrumbs_to_cloud,
    collection_to_cloud,
    collections_bulk_to_cloud,
    collections_from_us,
    structure_items_to_cloud,
)
from app.adapters.common import dump_model
from app.auth import AuthContext
from app.clients.auth import get_user_access_token
from app.clients.us import get_us_client
from app.models.generated import (
    Collection,
    CreateCollectionArgs,
    CreateCollectionResult,
    DeleteCollectionArgs,
    DeleteCollectionResult,
    DeleteCollectionsArgs,
    DeleteCollectionsResult,
    GetCollectionArgs,
    GetCollectionBreadcrumbsArgs,
    GetCollectionBreadcrumbsResult,
    GetCollectionResult,
    GetCollectionsByIdsArgs,
    GetRootCollectionPermissionsResult,
    GetStructureItemsArgs,
    GetStructureItemsResult,
    MoveCollectionArgs,
    MoveCollectionsArgs,
    UpdateCollectionArgs,
)


class GetRootCollectionPermissionsArgs(BaseModel):
    pass


class MoveCollectionsResult(BaseModel):
    collections: list[Collection]


def _us_list_params(payload: dict) -> dict:
    params = dict(payload)
    page_size = params.get("pageSize")
    if page_size is not None:
        params["pageSize"] = int(page_size)
    page = params.get("page")
    if page is not None and str(page).isdigit():
        params["page"] = int(page)
    return params


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
    token = await get_user_access_token()
    return await get_us_client().request(
        method,
        path,
        params=params,
        json=json,
        headers={"Authorization": f"Bearer {token}"},
    )


async def create_collection(
    args: CreateCollectionArgs, _ctx: AuthContext
) -> CreateCollectionResult:
    payload = args.model_dump(by_alias=True, mode="json")
    raw = await _us_private("POST", "/private/v1/collections", json=payload)
    return CreateCollectionResult.model_validate(collection_to_cloud(raw))


async def get_collection(
    args: GetCollectionArgs, _ctx: AuthContext
) -> GetCollectionResult:
    payload = dump_model(args)
    collection_id = payload.pop("collectionId")
    raw = await _us_private(
        "GET",
        f"/private/v1/collections/{collection_id}",
        params=payload,
    )
    return GetCollectionResult.model_validate(
        collection_to_cloud(raw, include_permissions=True)
    )


async def update_collection(args: UpdateCollectionArgs, _ctx: AuthContext) -> Collection:
    payload = dump_model(args)
    collection_id = payload.pop("collectionId")
    raw = await _us_public(
        "POST",
        f"/v1/collections/{collection_id}/update",
        json=payload,
    )
    return Collection.model_validate(collection_to_cloud(raw))


async def delete_collection(
    args: DeleteCollectionArgs, _ctx: AuthContext
) -> DeleteCollectionResult:
    collection_id = dump_model(args)["collectionId"]
    raw = await _us_public("DELETE", f"/v1/collections/{collection_id}")
    return DeleteCollectionResult.model_validate(
        collections_bulk_to_cloud(raw, ids=[collection_id])
    )


async def delete_collections(
    args: DeleteCollectionsArgs, _ctx: AuthContext
) -> DeleteCollectionsResult:
    payload = dump_model(args)
    raw = await _us_public("DELETE", "/v1/delete-collections", json=payload)
    return DeleteCollectionsResult.model_validate(
        collections_bulk_to_cloud(raw, ids=payload["collectionIds"])
    )


async def move_collection(args: MoveCollectionArgs, _ctx: AuthContext) -> Collection:
    payload = args.model_dump(by_alias=True, mode="json")
    collection_id = payload.pop("collectionId")
    raw = await _us_public(
        "POST",
        f"/v1/collections/{collection_id}/move",
        json=payload,
    )
    return Collection.model_validate(collection_to_cloud(raw))


async def move_collections(
    args: MoveCollectionsArgs, _ctx: AuthContext
) -> MoveCollectionsResult:
    payload = args.model_dump(by_alias=True, mode="json")
    raw = await _us_public("POST", "/v1/move-collections", json=payload)
    return MoveCollectionsResult.model_validate(
        collections_bulk_to_cloud(raw, ids=payload["collectionIds"])
    )


async def get_collections_by_ids(
    args: GetCollectionsByIdsArgs, _ctx: AuthContext
) -> list[Collection]:
    raw = await _us_public(
        "POST",
        "/v1/collections-get-list-by-ids",
        json=dump_model(args),
    )
    return [Collection.model_validate(item) for item in collections_from_us(raw)]


async def get_collection_content(
    args: GetStructureItemsArgs, _ctx: AuthContext
) -> GetStructureItemsResult:
    payload = dump_model(args)
    include_permissions = bool(payload.get("includePermissionsInfo"))
    raw = await _us_public(
        "GET",
        "/v1/structure-items",
        params=_us_list_params(payload),
    )
    return GetStructureItemsResult.model_validate(
        structure_items_to_cloud(raw, include_permissions=include_permissions)
    )


async def get_collection_breadcrumbs(
    args: GetCollectionBreadcrumbsArgs, _ctx: AuthContext
) -> GetCollectionBreadcrumbsResult:
    payload = dump_model(args)
    collection_id = payload.pop("collectionId")
    include_permissions = bool(payload.get("includePermissionsInfo"))
    raw = await _us_public(
        "GET",
        f"/v1/collections/{collection_id}/breadcrumbs",
        params=payload,
    )
    return GetCollectionBreadcrumbsResult.model_validate(
        breadcrumbs_to_cloud(raw, include_permissions=include_permissions)
    )


async def get_root_collection_permissions(
    _args: GetRootCollectionPermissionsArgs, _ctx: AuthContext
) -> GetRootCollectionPermissionsResult:
    raw = await _us_public("GET", "/v1/root-collection-permissions")
    return GetRootCollectionPermissionsResult.model_validate(
        {
            "createCollectionInRoot": bool(raw.get("createCollectionInRoot")),
            "createWorkbookInRoot": bool(raw.get("createWorkbookInRoot")),
        }
    )
