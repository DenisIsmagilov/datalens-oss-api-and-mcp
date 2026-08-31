from app.adapters.common import WORKBOOK_PERMISSIONS_ALL
from app.adapters.workbook import workbook_to_cloud

COLLECTION_PERMISSIONS_ALL = {
    "listAccessBindings": True,
    "updateAccessBindings": True,
    "createSharedEntry": True,
    "createCollection": True,
    "createWorkbook": True,
    "limitedView": True,
    "view": True,
    "update": True,
    "copy": True,
    "move": True,
    "delete": True,
}


def fill_collection_permissions(raw: dict | None) -> dict:
    filled = dict(COLLECTION_PERMISSIONS_ALL)
    if isinstance(raw, dict):
        filled.update(raw)
    return filled


def collection_to_cloud(raw: dict, *, include_permissions: bool = False) -> dict:
    item = {
        "collectionId": raw["collectionId"],
        "title": raw.get("title") or "",
        "description": raw.get("description"),
        "parentId": raw.get("parentId"),
        "tenantId": raw.get("tenantId") or "common",
        "createdBy": raw.get("createdBy") or "",
        "createdAt": raw.get("createdAt") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "meta": raw.get("meta") or {},
    }
    permissions = raw.get("permissions")
    if include_permissions or permissions is not None:
        item["permissions"] = fill_collection_permissions(permissions)
    return item


def _minimal_collection_raw(collection_id: str) -> dict:
    return {"collectionId": collection_id, "title": ""}


def collections_from_us(raw: dict | list) -> list[dict]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if raw.get("collections"):
            items = raw["collections"]
        elif raw.get("collectionId"):
            items = [raw]
        else:
            items = []
    else:
        items = []
    return [collection_to_cloud(item) for item in items]


def collections_bulk_to_cloud(
    raw: dict | list, *, ids: list[str] | None = None
) -> dict:
    items = collections_from_us(raw)
    if not items and ids:
        items = [collection_to_cloud(_minimal_collection_raw(item_id)) for item_id in ids]
    return {"collections": items}


def breadcrumbs_to_cloud(raw: dict | list, *, include_permissions: bool = False) -> list:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("breadcrumbs") or raw.get("collections") or []
        if not items and raw.get("collectionId"):
            items = [raw]
    else:
        items = []
    return [
        collection_to_cloud(item, include_permissions=include_permissions)
        for item in items
    ]


def _entry_structure_to_cloud(raw: dict) -> dict:
    item = {
        "entryId": raw["entryId"],
        "scope": raw["scope"],
        "type": raw.get("type") or "",
        "key": raw.get("key") or "",
        "displayKey": raw.get("displayKey") or raw.get("key") or "",
        "title": raw.get("title") or raw.get("displayKey") or raw.get("key") or "",
        "collectionId": raw.get("collectionId") or "",
        "workbookId": raw.get("workbookId"),
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "entity": "entry",
    }
    if raw.get("permissions") is not None:
        item["permissions"] = raw["permissions"]
    return item


def structure_item_to_cloud(raw: dict, *, include_permissions: bool = False) -> dict:
    entity = raw.get("entity")
    if entity == "entry":
        return _entry_structure_to_cloud(raw)
    if entity == "collection" or (
        entity is None and "workbookId" not in raw and raw.get("collectionId")
    ):
        item = collection_to_cloud(raw, include_permissions=include_permissions)
        item["entity"] = "collection"
        return item
    item = workbook_to_cloud(raw, include_permissions=include_permissions)
    item["entity"] = "workbook"
    if include_permissions and "permissions" not in item:
        item["permissions"] = dict(WORKBOOK_PERMISSIONS_ALL)
    return item


def structure_items_to_cloud(raw: dict, *, include_permissions: bool = False) -> dict:
    return {
        "items": [
            structure_item_to_cloud(item, include_permissions=include_permissions)
            for item in raw.get("items") or []
        ],
        "nextPageToken": raw.get("nextPageToken"),
    }
