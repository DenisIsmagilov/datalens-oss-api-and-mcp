import json
from datetime import datetime, timezone
from typing import Any

from app.adapters.data_result import clip
from app.models.rpc_data import Column

TABLE_NODES = {"table_wizard_node", "table_ql_node"}
METRIC_NODES = {"metric_wizard_node", "metric2_ql_node", "metric_ql_node"}
GRAPH_NODES = {"graph_wizard_node", "graph_ql_node"}
GRAPH_SERIES_TYPES = {"line", "spline", "area", "areaspline", "column", "bar"}
UNSUPPORTED_NOTE = "Визуализация не нормализуется: используйте queryDataset по datasetIds"


def markup_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(markup_text(item) for item in value)
    if isinstance(value, dict):
        for key in ("children", "content", "value"):
            if key in value:
                return markup_text(value[key])
        return ""
    return str(value)


def _title(body: dict) -> str:
    key = str(body.get("key") or "")
    return key.rsplit("/", 1)[-1] or str(body.get("id") or "")


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _dataset_ids(body: dict) -> list[str]:
    # у QL-чартов extra.datasets содержит id подключения, а не датасета
    if str(body.get("type") or "").endswith("_ql_node"):
        return []
    return [
        str(item["id"])
        for item in _list(_dict(body.get("extra")).get("datasets"))
        if isinstance(item, dict) and item.get("id")
    ]


def _leaf_heads(heads: list, prefix: str = "") -> list[tuple[str, str]]:
    leaves: list[tuple[str, str]] = []
    for head in heads:
        if not isinstance(head, dict):
            continue
        name = str(head.get("name") or head.get("id") or "")
        full = f"{prefix} / {name}" if prefix else name
        sub = head.get("sub")
        if isinstance(sub, list) and sub:
            leaves.extend(_leaf_heads(sub, full))
        else:
            leaves.append((full, str(head.get("type") or "")))
    return leaves


def _cell_value(cell: Any) -> Any:
    if not isinstance(cell, dict):
        return cell
    value = cell.get("value")
    if isinstance(value, (dict, list)):
        return markup_text(value)
    return value


def _table(data: dict) -> tuple[list[Column], list[list[Any]]]:
    columns = [Column(title=t, dataType=d) for t, d in _leaf_heads(_list(data.get("head")))]
    rows = [
        [_cell_value(cell) for cell in _list(row.get("cells"))]
        for row in _list(data.get("rows"))
        if isinstance(row, dict)
    ]
    return columns, rows


def _metric(data: list) -> tuple[list[Column], list[list[Any]]]:
    items = [item for item in data if isinstance(item, dict)]
    columns = [
        Column(title=str(item.get("title") or f"value{index}"), dataType="string")
        for index, item in enumerate(items)
    ]
    row = [_dict(_dict(item.get("content")).get("current")).get("value") for item in items]
    return columns, [row] if items else []


def _highcharts(body: dict) -> dict:
    raw = body.get("highchartsConfig")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _ms_to_datetime(ms: Any) -> datetime | None:
    if not isinstance(ms, (int, float)) or isinstance(ms, bool):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OverflowError, ValueError, OSError):
        return None


def _is_midnight(moment: datetime) -> bool:
    return (moment.hour, moment.minute, moment.second, moment.microsecond) == (0, 0, 0, 0)


def _category_index(x: Any, size: int) -> int | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return x if isinstance(x, int) and 0 <= x < size else None


def _point(point: Any) -> tuple[Any, Any]:
    if isinstance(point, dict):
        return point.get("x"), point.get("y")
    if isinstance(point, list) and len(point) == 2:
        return point[0], point[1]
    return None, point


def _graph(body: dict, data: dict) -> tuple[str, list[Column], list[list[Any]]] | None:
    graphs = [g for g in _list(data.get("graphs")) if isinstance(g, dict)]
    types = {str(g.get("type") or "line") for g in graphs}
    if not graphs or not types <= GRAPH_SERIES_TYPES:
        return None
    x_axis = _highcharts(body).get("xAxis")
    if isinstance(x_axis, list):
        x_axis = x_axis[0] if x_axis else None
    is_datetime = isinstance(x_axis, dict) and x_axis.get("type") == "datetime"
    categories = data.get("categories") if isinstance(data.get("categories"), list) else None
    rows: list[list[Any]] = []
    for graph in graphs:
        series = graph.get("title") or graph.get("name") or ""
        for index, point in enumerate(_list(graph.get("data"))):
            x, y = _point(point)
            if is_datetime:
                x = _ms_to_datetime(x)
            elif categories is not None:
                position = index if x is None else _category_index(x, len(categories))
                if position is not None and position < len(categories):
                    x = categories[position]
            rows.append([x, series, y])
    x_type = "string"
    if is_datetime:
        date_only = all(_is_midnight(row[0]) for row in rows if row[0] is not None)
        x_type = "date" if date_only else "datetime"
        for row in rows:
            if row[0] is not None:
                row[0] = (
                    row[0].date().isoformat()
                    if date_only
                    else row[0].isoformat().replace("+00:00", "Z")
                )
    columns = [
        Column(title="x", dataType=x_type),
        Column(title="series", dataType="string"),
        Column(title="value", dataType="float"),
    ]
    visualization = next(iter(types)) if len(types) == 1 else "mixed"
    return visualization, columns, rows


def normalize_chart(body: dict, *, max_rows: int, max_chars: int) -> dict:
    node = str(body.get("type") or "")
    data = body.get("data")
    base = {"title": _title(body), "datasetIds": _dataset_ids(body)}
    result: tuple[str, list[Column], list[list[Any]]] | None = None
    if node in TABLE_NODES and isinstance(data, dict) and "head" in data:
        result = ("table", *_table(data))
    elif node in METRIC_NODES and isinstance(data, list):
        result = ("metric", *_metric(data))
    elif node in GRAPH_NODES and isinstance(data, dict) and "graphs" in data:
        result = _graph(body, data)
    if result is None:
        return {
            **base,
            "visualization": node.removesuffix("_node") or "unknown",
            "columns": [],
            "rows": [],
            "rowCount": 0,
            "truncated": False,
            "normalized": False,
            "note": UNSUPPORTED_NOTE,
        }
    visualization, columns, rows = result
    truncated = len(rows) > max_rows
    clipped = [[clip(value, max_chars) for value in row] for row in rows[:max_rows]]
    return {
        **base,
        "visualization": visualization,
        "columns": columns,
        "rows": clipped,
        "rowCount": len(clipped),
        "truncated": truncated,
        "normalized": True,
    }
