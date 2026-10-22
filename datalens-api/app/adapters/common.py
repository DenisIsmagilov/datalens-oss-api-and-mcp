from datetime import datetime, timezone
from typing import Any

WORKBOOK_PERMISSIONS_ALL = {
    "listAccessBindings": True,
    "updateAccessBindings": True,
    "limitedView": True,
    "view": True,
    "update": True,
    "copy": True,
    "move": True,
    "publish": True,
    "embed": True,
    "delete": True,
}


def dump_model(model: Any) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


def dump_dashboard_model(model: Any) -> dict[str, Any]:
    """Dump a dashboard payload, keeping selector nulls United Storage needs.

    ``exclude_none`` stays in effect for the rest of the body. An explicit
    ``impactTabsIds: null`` and any explicit null inside ``source`` are kept.
    A key that was absent on input is not added.
    """
    raw = model.model_dump(by_alias=True, exclude_unset=True, mode="json")
    return _strip_nulls_except_selector_state(raw)


def _strip_nulls_except_selector_state(node: Any, *, in_source: bool = False) -> Any:
    if isinstance(node, list):
        return [
            _strip_nulls_except_selector_state(item, in_source=in_source) for item in node
        ]
    if not isinstance(node, dict):
        return node
    kept: dict[str, Any] = {}
    for key, value in node.items():
        if key == "source" and isinstance(value, dict):
            kept[key] = _strip_nulls_except_selector_state(value, in_source=True)
            continue
        if isinstance(value, dict):
            value = _strip_nulls_except_selector_state(value, in_source=in_source)
        elif isinstance(value, list):
            value = [
                _strip_nulls_except_selector_state(item, in_source=in_source)
                for item in value
            ]
        if value is None and not in_source and key != "impactTabsIds":
            continue
        kept[key] = value
    return kept


def _iso_to_unix_seconds(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return str(int(dt.timestamp()))


def _valid_unix_seconds(value: Any) -> str | None:
    if value is None:
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    if seconds < 1_000_000_000:
        return None
    return str(seconds)


def _timestamp_seconds(raw_ts: Any, fallback_iso: Any) -> str:
    if isinstance(raw_ts, dict):
        valid = _valid_unix_seconds(raw_ts.get("seconds"))
        if valid is not None:
            return valid
    iso = _iso_to_unix_seconds(fallback_iso)
    if iso is not None:
        return iso
    return "0"


def normalize_operation(raw: dict | None, *, workbook: dict | None = None) -> dict:
    source = raw if isinstance(raw, dict) else {}
    wb = workbook if isinstance(workbook, dict) else {}
    created_at = _timestamp_seconds(source.get("createdAt"), wb.get("createdAt"))
    modified_at = _timestamp_seconds(
        source.get("modifiedAt"), wb.get("updatedAt") or wb.get("createdAt")
    )
    return {
        "id": source.get("id") or wb.get("workbookId") or "",
        "description": source.get("description") or "Datalens operation",
        "createdBy": source.get("createdBy")
        if source.get("createdBy") is not None
        else (wb.get("createdBy") or ""),
        "createdAt": {"seconds": created_at},
        "modifiedAt": {"seconds": modified_at},
        "metadata": source.get("metadata")
        if isinstance(source.get("metadata"), dict)
        else {},
        "done": True if source.get("done") is None else bool(source["done"]),
    }
