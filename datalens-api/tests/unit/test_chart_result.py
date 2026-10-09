import json

import pytest

from app.adapters.chart_result import UNSUPPORTED_NOTE, markup_text, normalize_chart

COMMON = {
    "key": "1234/Отчёты/Выручка по дням",
    "extra": {"datasets": [{"id": "ds123", "fieldsList": []}]},
    "sources": {"x": {"url": "/_bi_datasets/ds123/pivot", "sql_query": "SELECT secret"}},
}


def _norm(body: dict, max_rows: int = 500) -> dict:
    return normalize_chart({**COMMON, **body}, max_rows=max_rows, max_chars=500)


def test_wizard_table_with_markup_cell():
    result = _norm({
        "type": "table_wizard_node",
        "data": {
            "head": [{"id": "c1", "name": "Город", "type": "text"}, {"id": "c2", "name": "Сумма", "type": "number"}],
            "rows": [
                {"cells": [{"value": "Москва", "fieldId": "c1"}, {"value": 10.5, "fieldId": "c2"}]},
                {"cells": [{"value": {"type": "bold", "children": ["Ка", {"type": "i", "children": ["зань"]}]}, "fieldId": "c1", "type": "markup"}, {"value": 3, "fieldId": "c2"}]},
            ],
        },
    })
    assert result["visualization"] == "table"
    assert result["normalized"] is True
    assert result["title"] == "Выручка по дням"
    assert result["datasetIds"] == ["ds123"]
    assert [c.title for c in result["columns"]] == ["Город", "Сумма"]
    assert result["rows"] == [["Москва", 10.5], ["Казань", 3]]
    assert "SELECT" not in json.dumps(result, default=str)


def test_pivot_head_uses_leaves_with_prefix():
    result = _norm({
        "type": "table_wizard_node",
        "data": {
            "head": [
                {"id": "r", "name": "Город", "type": "text"},
                {"id": "g", "name": "2026", "sub": [{"id": "a", "name": "Янв", "type": "number"}, {"id": "b", "name": "Фев", "type": "number"}]},
            ],
            "rows": [{"cells": [{"value": "Москва"}, {"value": 1}, {"value": 2}]}],
        },
    })
    assert [c.title for c in result["columns"]] == ["Город", "2026 / Янв", "2026 / Фев"]
    assert result["rows"] == [["Москва", 1, 2]]


def test_ql_table_metadata_is_ignored():
    result = _norm({
        "type": "table_ql_node",
        "data": {
            "head": [{"id": "t", "name": "table", "type": "text"}],
            "rows": [{"cells": [{"value": "orders", "fieldId": "t"}]}],
            "metadata": {"distincts": {"table": ["orders", "secret_table"]}},
        },
    })
    assert result["rows"] == [["orders"]]
    assert "secret_table" not in json.dumps(result, default=str)


def test_metric_wizard_and_ql():
    for node in ("metric_wizard_node", "metric2_ql_node"):
        result = _norm({"type": node, "data": [{"content": {"current": {"value": "42"}}, "title": "Заказы", "metadata": {"distincts": {"x": ["s"]}}}]})
        assert result["visualization"] == "metric"
        assert [c.title for c in result["columns"]] == ["Заказы"]
        assert result["rows"] == [["42"]]


def test_graph_datetime_axis_long_table():
    result = _norm({
        "type": "graph_wizard_node",
        "highchartsConfig": json.dumps({"xAxis": {"type": "datetime"}}),
        "data": {"graphs": [
            {"title": "Москва", "type": "area", "data": [{"x": 1788220800000, "y": 41000.0}, {"x": 1788307200000, "y": 1.5}]},
            {"title": "Казань", "type": "area", "data": [{"x": 1788220800000, "y": 7}]},
        ]},
    })
    assert result["visualization"] == "area"
    assert [(c.title, c.dataType) for c in result["columns"]] == [("x", "date"), ("series", "string"), ("value", "float")]
    assert result["rows"] == [["2026-09-01", "Москва", 41000.0], ["2026-09-02", "Москва", 1.5], ["2026-09-01", "Казань", 7]]


def test_graph_hourly_axis_is_uniform_datetime():
    result = _norm({
        "type": "graph_wizard_node",
        "highchartsConfig": json.dumps({"xAxis": {"type": "datetime"}}),
        "data": {"graphs": [{"title": "s", "type": "line", "data": [{"x": 1788220800000, "y": 1}, {"x": 1788224400000, "y": 2}]}]},
    })
    assert result["columns"][0].dataType == "datetime"
    assert [row[0] for row in result["rows"]] == ["2026-09-01T00:00:00Z", "2026-09-01T01:00:00Z"]


def test_graph_category_index_ignores_bool_and_accepts_integral_float():
    result = _norm({
        "type": "graph_wizard_node",
        "data": {"categories": ["a", "b"], "graphs": [{"title": "s", "type": "line", "data": [{"x": True, "y": 1}, {"x": 1.0, "y": 2}]}]},
    })
    assert [row[0] for row in result["rows"]] == [True, "b"]


def test_ql_chart_has_no_dataset_ids():
    result = _norm({"type": "metric2_ql_node", "data": [{"content": {"current": {"value": "1"}}}]})
    assert result["datasetIds"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"type": "table_wizard_node", "extra": {"datasets": None}, "data": {"head": None, "rows": None}},
        {"type": "table_wizard_node", "extra": "x", "data": {"head": [], "rows": [{"cells": None}, "junk"]}},
        {"type": "metric_wizard_node", "data": [{"content": "x"}, {"content": {"current": "x"}}, {}]},
        {"type": "graph_wizard_node", "highchartsConfig": "{not json", "data": {"graphs": [{"data": None}]}},
        {
            "type": "graph_wizard_node",
            "highchartsConfig": json.dumps({"xAxis": {"type": "datetime"}}),
            "data": {"graphs": [{"title": "s", "data": [{"x": 1e20, "y": 1}, {"x": float("nan"), "y": 2}]}]},
        },
        {"type": "graph_wizard_node", "data": None},
        {"type": None, "data": None, "key": None},
    ],
)
def test_odd_shapes_do_not_crash(body):
    result = _norm(body)
    assert isinstance(result["rows"], list)
    json.dumps(result, default=str, allow_nan=False)


def test_graph_category_axis_by_index_and_order():
    result = _norm({
        "type": "graph_ql_node",
        "highchartsConfig": json.dumps({"xAxis": {"type": "category"}}),
        "data": {
            "categories": ["Янв", "Фев"],
            "graphs": [
                {"title": "План", "type": "column", "data": [{"x": 0, "y": 1}, {"x": 1, "y": 2}]},
                {"title": "Факт", "type": "column", "data": [{"y": 3}, {"y": 4}]},
            ],
        },
    })
    assert result["visualization"] == "column"
    assert result["rows"] == [["Янв", "План", 1], ["Фев", "План", 2], ["Янв", "Факт", 3], ["Фев", "Факт", 4]]


def test_graph_mixed_types():
    result = _norm({
        "type": "graph_wizard_node",
        "data": {"graphs": [{"title": "a", "type": "line", "data": [{"x": "k", "y": 1}]}, {"title": "b", "type": "column", "data": [{"x": "k", "y": 2}]}]},
    })
    assert result["visualization"] == "mixed" and result["normalized"] is True


def test_unsupported_types():
    pie_graph = _norm({"type": "graph_wizard_node", "data": {"graphs": [{"title": "a", "type": "pie", "data": [{"y": 1}]}]}})
    d3 = _norm({"type": "d3_wizard_node", "data": {"series": {"data": [{"type": "pie", "data": [{"name": "x", "value": 1}]}]}}})
    for result in (pie_graph, d3):
        assert result["normalized"] is False
        assert result["rows"] == [] and result["columns"] == [] and result["rowCount"] == 0
        assert result["note"] == UNSUPPORTED_NOTE
        assert result["datasetIds"] == ["ds123"]
    assert d3["visualization"] == "d3_wizard"


def test_rows_truncated_to_max_rows():
    rows = [{"cells": [{"value": i}]} for i in range(5)]
    result = _norm({"type": "table_wizard_node", "data": {"head": [{"id": "n", "name": "n", "type": "number"}], "rows": rows}}, max_rows=3)
    assert result["rowCount"] == 3 and result["truncated"] is True


def test_markup_text_shapes():
    assert markup_text(None) == ""
    assert markup_text({"content": "a"}) == "a"
    assert markup_text([{"children": ["b"]}, "c"]) == "bc"
