from typing import Any

from app.adapters.entries import fill_entry_permissions
from app.errors import ApiError

_DROP = {
    "unversionedData",
    "mirrored",
    "sourceVersion",
    "isDeleted",
    "deletedAt",
}

_KEEP = (
    "entryId",
    "scope",
    "type",
    "key",
    "createdBy",
    "createdAt",
    "updatedBy",
    "updatedAt",
    "savedId",
    "publishedId",
    "revId",
    "tenantId",
    "data",
    "meta",
    "annotation",
    "hidden",
    "public",
    "workbookId",
    "collectionId",
    "links",
    "isFavorite",
)


def entry_to_chart(raw: dict) -> dict[str, Any]:
    if not isinstance(raw, dict) or "entryId" not in raw:
        raise ApiError(500, "INTERNAL", "US entry missing entryId")
    item: dict[str, Any] = {key: raw[key] for key in _KEEP if key in raw}
    if raw.get("permissions") is not None:
        item["permissions"] = fill_entry_permissions(raw.get("permissions"))
    for key in _DROP:
        item.pop(key, None)
    return item
