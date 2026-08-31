from typing import Any

ENTRY_PERMISSIONS_ALL = {
    "execute": True,
    "read": True,
    "edit": True,
    "admin": True,
}

ENTRY_PERMISSIONS_NONE = {
    "execute": False,
    "read": False,
    "edit": False,
    "admin": False,
}


def fill_entry_permissions(raw: dict | None, *, default: dict | None = None) -> dict:
    filled = dict(default if default is not None else ENTRY_PERMISSIONS_NONE)
    if isinstance(raw, dict):
        for key in ENTRY_PERMISSIONS_NONE:
            if key in raw:
                filled[key] = bool(raw[key])
    return filled


def name_from_key(key: str | None, fallback: str = "") -> str:
    if not key:
        return fallback
    parts = [part for part in str(key).split("/") if part]
    return parts[-1] if parts else fallback


def _as_list(raw: dict | list) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("entries", "relations", "items"):
            if isinstance(raw.get(key), list):
                return raw[key]
        if raw.get("entryId"):
            return [raw]
    return []


def relation_to_cloud(raw: dict) -> dict:
    item = {
        "entryId": raw["entryId"],
        "key": raw.get("key"),
        "scope": raw.get("scope") or "folder",
        "type": raw.get("type") or "",
        "createdAt": raw.get("createdAt") or "",
        "public": bool(raw["public"]) if "public" in raw else False,
        "tenantId": raw.get("tenantId"),
        "workbookId": raw.get("workbookId"),
        "collectionId": raw.get("collectionId"),
    }
    if "isLocked" in raw:
        item["isLocked"] = bool(raw["isLocked"])
    if raw.get("permissions") is not None:
        item["permissions"] = fill_entry_permissions(raw.get("permissions"))
    if raw.get("fullPermissions") is not None:
        item["fullPermissions"] = raw["fullPermissions"]
    return item


def relations_to_cloud(raw: dict | list) -> dict:
    if isinstance(raw, list):
        relations = raw
        next_page = None
    else:
        relations = raw.get("relations") or []
        next_page = raw.get("nextPageToken")
    return {
        "relations": [relation_to_cloud(item) for item in relations],
        "nextPageToken": next_page,
    }


def rename_entry_to_cloud(raw: dict) -> dict:
    return {
        "entryId": raw["entryId"],
        "key": raw.get("key") or raw.get("displayKey") or "",
        "scope": raw.get("scope") or "folder",
        "type": raw.get("type") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
    }


def rename_result_to_cloud(raw: dict | list) -> list[dict]:
    return [rename_entry_to_cloud(item) for item in _as_list(raw)]


def get_entries_item_to_cloud(raw: dict) -> dict:
    if raw.get("isLocked") is True:
        return {
            "isLocked": True,
            "entryId": raw["entryId"],
            "scope": raw.get("scope") or "folder",
            "type": raw.get("type") or "",
            "name": raw.get("name") or name_from_key(raw.get("key") or raw.get("displayKey")),
        }
    item = {
        "entryId": raw["entryId"],
        "key": raw.get("key") or raw.get("displayKey") or "",
        "scope": raw.get("scope") or "folder",
        "type": raw.get("type") or "",
        "meta": raw.get("meta"),
        "createdAt": raw.get("createdAt") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "createdBy": raw.get("createdBy") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "savedId": raw.get("savedId") or raw.get("revId") or "",
        "publishedId": raw.get("publishedId"),
        "hidden": bool(raw["hidden"]) if "hidden" in raw else False,
        "workbookId": raw.get("workbookId"),
        "collectionId": raw.get("collectionId"),
        "isFavorite": bool(raw["isFavorite"]) if "isFavorite" in raw else False,
        "links": raw.get("links"),
        "name": raw.get("name") or name_from_key(raw.get("key") or raw.get("displayKey")),
    }
    if raw.get("workbookTitle") is not None:
        item["workbookTitle"] = raw["workbookTitle"]
    if raw.get("collectionTitle") is not None:
        item["collectionTitle"] = raw["collectionTitle"]
    if "isLocked" in raw:
        item["isLocked"] = False
    if raw.get("permissions") is not None:
        item["permissions"] = fill_entry_permissions(raw.get("permissions"))
    if raw.get("data") is not None:
        item["data"] = raw["data"]
    return item


def get_entries_v2_to_cloud(raw: dict | list) -> dict:
    if isinstance(raw, list):
        entries = raw
        next_page = None
    else:
        entries = raw.get("entries") or []
        next_page = raw.get("nextPageToken")
    return {
        "entries": [get_entries_item_to_cloud(item) for item in entries],
        "nextPageToken": next_page,
    }


def list_directory_entry_to_cloud(raw: dict) -> dict:
    item = {
        "entryId": raw["entryId"],
        "key": raw.get("key") or raw.get("displayKey") or "",
        "scope": raw.get("scope") or "folder",
        "type": raw.get("type") or "",
        "meta": raw.get("meta"),
        "createdAt": raw.get("createdAt") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "createdBy": raw.get("createdBy") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "savedId": raw.get("savedId") or raw.get("revId") or "",
        "publishedId": raw.get("publishedId"),
        "hidden": bool(raw["hidden"]) if "hidden" in raw else False,
        "workbookId": raw.get("workbookId") or "",
        "collectionId": raw.get("collectionId"),
        "isFavorite": bool(raw["isFavorite"]) if "isFavorite" in raw else False,
        "isLocked": bool(raw["isLocked"]) if "isLocked" in raw else False,
        "name": raw.get("name") or name_from_key(raw.get("key") or raw.get("displayKey")),
    }
    if raw.get("workbookTitle") is not None:
        item["workbookTitle"] = raw["workbookTitle"]
    if raw.get("collectionTitle") is not None:
        item["collectionTitle"] = raw["collectionTitle"]
    if raw.get("permissions") is not None:
        item["permissions"] = fill_entry_permissions(raw.get("permissions"))
    return item


def breadcrumb_to_cloud(raw: dict) -> dict:
    return {
        "title": raw.get("title") or name_from_key(raw.get("path") or raw.get("key")),
        "path": raw.get("path") or raw.get("key") or "",
        "entryId": raw["entryId"],
        "isLocked": bool(raw["isLocked"]) if "isLocked" in raw else False,
        "permissions": fill_entry_permissions(
            raw.get("permissions"), default=ENTRY_PERMISSIONS_ALL
        ),
    }


def list_directory_to_cloud(raw: dict | list) -> dict:
    if isinstance(raw, list):
        entries = raw
        crumbs = []
        has_next = False
    else:
        entries = raw.get("entries") or []
        crumbs = raw.get("breadCrumbs") or raw.get("breadcrumbs") or []
        has_next = bool(raw.get("hasNextPage"))
        if not has_next:
            has_next = bool(raw.get("nextPageToken"))
    return {
        "hasNextPage": has_next,
        "breadCrumbs": [breadcrumb_to_cloud(item) for item in crumbs],
        "entries": [list_directory_entry_to_cloud(item) for item in entries],
    }


def create_folder_to_cloud(raw: dict) -> dict:
    return {
        "entryId": raw["entryId"],
        "scope": "folder",
        "type": "",
        "key": raw.get("key") or raw.get("displayKey") or "",
        "unversionedData": raw.get("unversionedData") or {},
        "createdBy": raw.get("createdBy") or "",
        "createdAt": raw.get("createdAt") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "savedId": raw.get("savedId") or raw.get("revId") or "",
        "revId": raw.get("revId") or raw.get("savedId") or "",
        "publishedId": raw.get("publishedId"),
        "tenantId": raw.get("tenantId") or "common",
        "data": raw.get("data") or {},
        "meta": raw.get("meta") or {},
        "annotation": None,
        "hidden": bool(raw["hidden"]) if "hidden" in raw else False,
        "mirrored": bool(raw["mirrored"]) if "mirrored" in raw else False,
        "public": bool(raw["public"]) if "public" in raw else False,
        "workbookId": None,
        "collectionId": None,
        "version": None,
        "sourceVersion": None,
        "links": None,
    }


def move_entry_to_cloud(raw: dict) -> dict:
    return {
        "entryId": raw["entryId"],
        "key": raw.get("key") or raw.get("displayKey") or "",
        "scope": raw.get("scope") or "folder",
        "type": raw.get("type") or "",
    }


def move_result_to_cloud(raw: dict | list) -> list[dict]:
    return [move_entry_to_cloud(item) for item in _as_list(raw)]


def _permissions_from_access(raw: dict) -> dict:
    if isinstance(raw.get("permissions"), dict) and any(
        key in raw["permissions"] for key in ENTRY_PERMISSIONS_NONE
    ):
        return fill_entry_permissions(raw["permissions"])
    return fill_entry_permissions(raw if any(key in raw for key in ENTRY_PERMISSIONS_NONE) else None)


def entries_permissions_item_to_cloud(raw: dict) -> dict:
    if raw.get("error") == "NOT_FOUND":
        return {"error": "NOT_FOUND"}
    return {"permissions": _permissions_from_access(raw)}


def get_permissions_to_cloud(raw: dict) -> dict:
    pending = raw.get("pendingPermissions")
    permissions = raw.get("permissions")
    dls_keys = ("acl_adm", "acl_edit", "acl_view", "acl_execute")
    if not isinstance(permissions, dict) or not any(key in permissions for key in dls_keys):
        permissions = {}
    if not isinstance(pending, dict):
        pending = {}
    return {
        "editable": bool(raw["editable"]) if "editable" in raw else False,
        "pendingPermissions": pending,
        "permissions": permissions,
    }


def flatten_query(payload: dict, *, drop: set[str] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    skip = drop or set()
    for key, value in payload.items():
        if key in skip or value is None:
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_value is not None:
                    params[f"{key}[{sub_key}]"] = sub_value
        else:
            params[key] = value
    for key in ("page", "pageSize"):
        if params.get(key) is not None:
            params[key] = int(params[key])
    return params
