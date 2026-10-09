import json
from typing import Any

_MAX_QUERY_CHARS = 3000
_MAX_TEXT_CHARS = 300


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def title_from_key(key: Any) -> str:
    return str(key or "").rsplit("/", 1)[-1]


def compact_entries(body: dict) -> dict:
    entries = [
        {
            "entryId": entry.get("entryId"),
            "scope": entry.get("scope"),
            "type": entry.get("type"),
            "title": title_from_key(entry.get("key")),
        }
        for entry in _list(body.get("entries"))
        if isinstance(entry, dict)
    ]
    return {"entries": entries, "count": len(entries), "nextPageToken": body.get("nextPageToken")}


def _selectors(item: dict) -> list[dict]:
    data = _dict(item.get("data"))
    controls = _list(data.get("group")) if item.get("type") == "group_control" else [data]
    selectors = []
    for control in controls:
        if not isinstance(control, dict):
            continue
        source = _dict(control.get("source"))
        selectors.append(
            {
                "title": control.get("title"),
                "params": sorted(_dict(control.get("defaults")).keys()),
                "sourceType": control.get("sourceType"),
                "datasetId": source.get("datasetId"),
                "fieldId": source.get("datasetFieldId") or source.get("fieldName"),
            }
        )
    return selectors


def compact_dashboard(body: dict) -> dict:
    entry = _dict(body.get("entry"))
    tabs = []
    for tab in _list(_dict(entry.get("data")).get("tabs")):
        if not isinstance(tab, dict):
            continue
        charts: list[dict] = []
        selectors: list[dict] = []
        texts: list[str] = []
        for item in _list(tab.get("items")):
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            data = _dict(item.get("data"))
            if kind == "widget":
                for widget_tab in _list(data.get("tabs")):
                    if isinstance(widget_tab, dict) and widget_tab.get("chartId"):
                        charts.append(
                            {
                                "title": widget_tab.get("title"),
                                "chartId": widget_tab.get("chartId"),
                                "params": _dict(widget_tab.get("params")),
                            }
                        )
            elif kind in ("control", "group_control"):
                selectors.extend(_selectors(item))
            elif kind in ("title", "text"):
                text = str(data.get("text") or "")[:_MAX_TEXT_CHARS]
                if text:
                    texts.append(text)
        tabs.append(
            {"id": tab.get("id"), "title": tab.get("title"), "charts": charts, "selectors": selectors, "texts": texts}
        )
    return {
        "dashboardId": entry.get("entryId"),
        "title": title_from_key(entry.get("key")),
        "workbookId": entry.get("workbookId"),
        "description": _dict(entry.get("annotation")).get("description") or "",
        "tabs": tabs,
    }


def _shared(body: dict) -> dict:
    raw = _dict(body.get("data")).get("shared")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return _dict(raw)


def _placeholder_fields(node: Any, out: dict[str, list[str]]) -> None:
    if isinstance(node, list):
        for value in node:
            _placeholder_fields(value, out)
        return
    if not isinstance(node, dict):
        return
    items = node.get("items")
    if isinstance(items, list) and node.get("id") is not None:
        titles: list[str] = []
        for item in items:
            title = item.get("title") if isinstance(item, dict) else None
            if title and title not in titles:
                titles.append(title)
        if titles:
            out[str(node["id"])] = titles
    for key, value in node.items():
        if key != "items":
            _placeholder_fields(value, out)


def _visualization(shared: dict) -> tuple[Any, dict[str, list[str]]]:
    visualization = _dict(shared.get("visualization"))
    placeholders: dict[str, list[str]] = {}
    _placeholder_fields(visualization, placeholders)
    return visualization.get("id"), placeholders


def _wizard(shared: dict) -> dict:
    visualization, placeholders = _visualization(shared)
    filters = []
    for item in _list(shared.get("filters")):
        if isinstance(item, dict):
            condition = _dict(item.get("filter"))
            filters.append(
                {"field": item.get("title"), "operation": condition.get("operation"), "value": condition.get("value")}
            )
    return {
        "visualization": visualization,
        "datasetIds": [str(x) for x in _list(shared.get("datasetsIds"))],
        "placeholders": placeholders,
        "filters": filters,
        "colors": [c.get("title") for c in _list(shared.get("colors")) if isinstance(c, dict)],
        "sort": [s.get("title") for s in _list(shared.get("sort")) if isinstance(s, dict)],
    }


def _ql(shared: dict) -> dict:
    visualization, placeholders = _visualization(shared)
    return {
        "visualization": visualization,
        "query": str(shared.get("queryValue") or "")[:_MAX_QUERY_CHARS],
        "params": [p.get("name") for p in _list(shared.get("params")) if isinstance(p, dict)],
        "placeholders": placeholders,
    }


def compact_chart(body: dict, kind: str) -> dict:
    shared = _shared(body)
    base = {
        "chartId": body.get("entryId"),
        "title": title_from_key(body.get("key")),
        "kind": kind,
        "type": body.get("type"),
        "workbookId": body.get("workbookId"),
    }
    return {**base, **(_ql(shared) if kind == "ql" else _wizard(shared))}


def compact_dataset(body: dict) -> dict:
    dataset = _dict(body.get("dataset"))
    fields = []
    for item in _list(dataset.get("result_schema")):
        if not isinstance(item, dict) or item.get("hidden"):
            continue
        field = {
            "title": item.get("title"),
            "guid": item.get("guid"),
            "type": item.get("type"),
            "dataType": item.get("data_type"),
            "aggregation": item.get("aggregation"),
        }
        if item.get("description"):
            field["description"] = str(item["description"])[:_MAX_TEXT_CHARS]
        if item.get("calc_mode") == "formula":
            field["calculated"] = True
        fields.append(field)
    return {
        "datasetId": body.get("id"),
        "title": title_from_key(body.get("key")) or body.get("name"),
        "workbookId": body.get("workbook_id"),
        "description": dataset.get("description") or "",
        "fields": fields,
        "sources": [s.get("title") for s in _list(dataset.get("sources")) if isinstance(s, dict)],
    }
