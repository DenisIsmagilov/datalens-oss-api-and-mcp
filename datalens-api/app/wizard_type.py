import json
from typing import Any

from app.errors import ApiError

GRAPH_ENTRY_TYPE = "graph_wizard_node"
TABLE_ENTRY_TYPE = "table_wizard_node"
TABLE_VIS_IDS = frozenset({"flatTable", "pivotTable", "table"})


def _as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def extract_visualization_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    shared = _as_dict(data.get("shared"))
    if shared is None:
        return None
    visualization = shared.get("visualization")
    if not isinstance(visualization, dict):
        return None
    vis_id = visualization.get("id")
    if isinstance(vis_id, str) and vis_id:
        return vis_id
    return None


def resolve_wizard_entry_type(data: Any) -> str:
    vis_id = extract_visualization_id(data)
    if vis_id in TABLE_VIS_IDS:
        return TABLE_ENTRY_TYPE
    return GRAPH_ENTRY_TYPE


def encode_chart_data_for_us(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    shared = data.get("shared")
    if not isinstance(shared, dict):
        return data
    encoded = dict(data)
    encoded["shared"] = json.dumps(shared, ensure_ascii=False, indent=4)
    return encoded


def assert_wizard_type_compatible(entry_type: str, data: Any) -> None:
    vis_id = extract_visualization_id(data)
    if vis_id is None:
        return
    vis_is_table = vis_id in TABLE_VIS_IDS
    type_is_table = entry_type == TABLE_ENTRY_TYPE
    if vis_is_table == type_is_table:
        return
    expected = TABLE_ENTRY_TYPE if vis_is_table else GRAPH_ENTRY_TYPE
    raise ApiError(
        400,
        "INVALID_ARGUMENT",
        f"visualization.id={vis_id} is incompatible with entry.type={entry_type}; "
        f"expected {expected}",
    )
