from app.adapters.common import WORKBOOK_PERMISSIONS_ALL, normalize_operation


def fill_workbook_permissions(raw: dict | None) -> dict:
    filled = dict(WORKBOOK_PERMISSIONS_ALL)
    if isinstance(raw, dict):
        filled.update(raw)
    return filled


def workbook_to_cloud(raw: dict, *, include_permissions: bool = False) -> dict:
    item = {
        "workbookId": raw["workbookId"],
        "collectionId": raw.get("collectionId"),
        "title": raw["title"],
        "description": raw.get("description"),
        "tenantId": raw.get("tenantId") or "common",
        "meta": raw.get("meta") or {},
        "createdBy": raw.get("createdBy") or "",
        "createdAt": raw.get("createdAt") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "status": raw.get("status") or "active",
    }
    permissions = raw.get("permissions")
    if include_permissions or permissions is not None:
        item["permissions"] = fill_workbook_permissions(permissions)
    return item


def create_workbook_to_cloud(raw: dict) -> dict:
    item = workbook_to_cloud(raw, include_permissions=False)
    item["operation"] = normalize_operation(raw.get("operation"), workbook=raw)
    return item


def workbooks_from_us(raw: dict | list) -> list[dict]:
    if isinstance(raw, list):
        items = raw
    else:
        items = raw.get("workbooks") or []
    return [workbook_to_cloud(item) for item in items]


def workbooks_bulk_to_cloud(raw: dict | list) -> dict:
    return {"workbooks": workbooks_from_us(raw)}


def entry_to_cloud(raw: dict) -> dict:
    item = {
        "entryId": raw["entryId"],
        "scope": raw["scope"],
        "type": raw.get("type") or "",
        "key": raw.get("key"),
        "displayKey": raw.get("displayKey"),
        "createdBy": raw.get("createdBy") or "",
        "createdAt": raw.get("createdAt") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "savedId": raw.get("savedId"),
        "publishedId": raw.get("publishedId"),
        "revId": raw.get("revId") or "",
        "meta": raw.get("meta"),
        "hidden": raw.get("hidden"),
        "workbookId": raw.get("workbookId"),
        "collectionId": raw.get("collectionId"),
        "tenantId": raw.get("tenantId"),
        "isFavorite": bool(raw["isFavorite"]) if "isFavorite" in raw else False,
        "isLocked": bool(raw["isLocked"]) if "isLocked" in raw else False,
        "mirrored": raw.get("mirrored"),
    }
    if raw.get("permissions") is not None:
        item["permissions"] = raw["permissions"]
    return item


def entries_page_to_cloud(raw: dict) -> dict:
    return {
        "entries": [entry_to_cloud(item) for item in raw.get("entries") or []],
        "nextPageToken": raw.get("nextPageToken"),
    }


def workbooks_page_to_cloud(raw: dict, *, include_permissions: bool) -> dict:
    return {
        "workbooks": [
            workbook_to_cloud(item, include_permissions=include_permissions)
            for item in raw.get("workbooks") or []
        ],
        "nextPageToken": raw.get("nextPageToken"),
    }
