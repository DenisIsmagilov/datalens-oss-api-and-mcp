from typing import Any

from app.models.rpc_data import Column

ELLIPSIS = "…"


def clip(value: Any, max_chars: int) -> Any:
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + ELLIPSIS
    return value


def cast_value(value: Any, data_type: str, max_chars: int) -> Any:
    if value is None:
        return None
    if data_type == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    elif data_type == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    elif data_type == "boolean" and isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return clip(value, max_chars)


def parse_result(
    body: dict, *, role: str, limit: int, max_chars: int
) -> tuple[list[Column], list[list[Any]], bool]:
    meta = [
        field
        for field in body.get("fields", [])
        if isinstance(field, dict) and (field.get("role_spec") or {}).get("role") == role
    ]
    blocks = body.get("result_data") or []
    raw_rows = blocks[0].get("rows", []) if blocks else []
    rows: list[list[Any]] = []
    for raw in raw_rows:
        by_legend = dict(zip(raw.get("legend", []), raw.get("data", [])))
        rows.append(
            [
                cast_value(
                    by_legend.get(field.get("legend_item_id")),
                    str(field.get("data_type") or ""),
                    max_chars,
                )
                for field in meta
            ]
        )
    columns = [
        Column(
            title=str(field.get("title") or field.get("id") or ""),
            dataType=str(field.get("data_type") or ""),
        )
        for field in meta
    ]
    return columns, rows[:limit], len(rows) > limit
