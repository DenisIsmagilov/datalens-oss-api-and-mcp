from typing import Any

from app.errors import ApiError


def _require_export_id(raw: Any, *, what: str) -> str:
    if not isinstance(raw, dict) or raw.get("exportId") in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            f"meta-manager {what} response is missing exportId",
        )
    return raw["exportId"]


def export_id_to_cloud(raw: Any, *, what: str) -> dict:
    return {"exportId": _require_export_id(raw, what=what)}


def export_status_to_cloud(raw: Any) -> dict:
    export_id = _require_export_id(raw, what="export status")
    status = raw.get("status")
    if status in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            "meta-manager export status response is missing status",
        )
    item: dict[str, Any] = {
        "exportId": export_id,
        "status": status,
        "progress": 0 if raw.get("progress") is None else raw["progress"],
    }
    if "notifications" in raw:
        item["notifications"] = raw["notifications"]
    else:
        item["notifications"] = []
    return item


def _require_import_ids(raw: Any, *, what: str) -> tuple[str, str]:
    if not isinstance(raw, dict):
        raise ApiError(
            500,
            "INTERNAL",
            f"meta-manager {what} response is missing importId",
        )
    import_id = raw.get("importId")
    workbook_id = raw.get("workbookId")
    if import_id in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            f"meta-manager {what} response is missing importId",
        )
    if workbook_id in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            f"meta-manager {what} response is missing workbookId",
        )
    return import_id, workbook_id


def import_ids_to_cloud(raw: Any, *, what: str) -> dict:
    import_id, workbook_id = _require_import_ids(raw, what=what)
    return {"importId": import_id, "workbookId": workbook_id}


def import_status_to_cloud(raw: Any) -> dict:
    import_id, workbook_id = _require_import_ids(raw, what="import status")
    status = raw.get("status") if isinstance(raw, dict) else None
    if status in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            "meta-manager import status response is missing status",
        )
    item: dict[str, Any] = {
        "importId": import_id,
        "workbookId": workbook_id,
        "status": status,
        "progress": 0 if raw.get("progress") is None else raw["progress"],
    }
    if "notifications" in raw:
        item["notifications"] = raw["notifications"]
    else:
        item["notifications"] = []
    return item


def export_result_to_cloud(raw: Any) -> dict:
    export_id = _require_export_id(raw, what="export result")
    status = raw.get("status") if isinstance(raw, dict) else None
    if status in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            "meta-manager export result response is missing status",
        )
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        raise ApiError(
            500,
            "INTERNAL",
            "meta-manager export result response is missing data",
        )
    if "export" not in data or data["export"] is None:
        raise ApiError(
            500,
            "INTERNAL",
            "meta-manager export result response is missing data.export",
        )
    if "hash" not in data or data["hash"] is None:
        raise ApiError(
            500,
            "INTERNAL",
            "meta-manager export result response is missing data.hash",
        )
    return {
        "exportId": export_id,
        "status": status,
        "data": {
            "export": data["export"],
            "hash": data["hash"],
        },
    }
