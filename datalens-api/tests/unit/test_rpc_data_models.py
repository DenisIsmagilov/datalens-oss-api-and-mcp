import pytest
from pydantic import ValidationError

from app.models.rpc_data import (
    DataFilter,
    GetChartDataArgs,
    GetDatasetFieldValuesArgs,
    QueryDatasetArgs,
)


@pytest.mark.parametrize(
    ("op", "values"),
    [
        ("isnull", []),
        ("isnotnull", []),
        ("between", ["2026-01-01", "2026-02-01"]),
        ("in", ["a"]),
        ("nin", ["a", "b", "c"]),
        ("eq", [1]),
        ("icontains", ["моск"]),
    ],
)
def test_filter_value_counts_accepted(op, values):
    assert DataFilter(field="f", op=op, values=values).op == op


@pytest.mark.parametrize(
    ("op", "values"),
    [
        ("isnull", ["x"]),
        ("between", ["only-one"]),
        ("in", []),
        ("eq", []),
        ("eq", [1, 2]),
    ],
)
def test_filter_value_counts_rejected(op, values):
    with pytest.raises(ValidationError):
        DataFilter(field="f", op=op, values=values)


def test_unknown_op_rejected():
    with pytest.raises(ValidationError):
        DataFilter(field="f", op="lenlt", values=[1])


def test_query_defaults():
    args = QueryDatasetArgs(datasetId="abc123", fields=["Город"])
    assert args.limit == 100
    assert args.filters == [] and args.calculatedFields == [] and args.orderBy == []


@pytest.mark.parametrize(
    "payload",
    [
        {"datasetId": "abc", "fields": []},
        {"datasetId": "abc", "fields": [f"f{i}" for i in range(31)]},
        {"datasetId": "abc", "fields": ["a"], "limit": 0},
        {"datasetId": "abc", "fields": ["a"], "unexpected": 1},
        {"datasetId": "../x", "fields": ["a"]},
        {
            "datasetId": "abc",
            "fields": ["a"],
            "calculatedFields": [{"title": f"c{i}", "formula": "1"} for i in range(11)],
        },
    ],
)
def test_query_schema_limits(payload):
    with pytest.raises(ValidationError):
        QueryDatasetArgs.model_validate(payload)


def test_field_values_defaults():
    args = GetDatasetFieldValuesArgs(datasetId="abc", field="Склад")
    assert args.mode == "distinct" and args.limit == 100 and args.search is None


def test_chart_args_params_shapes():
    args = GetChartDataArgs(chartId="xyz789", params={"a": "1", "b": ["x", "y"]})
    assert args.params == {"a": "1", "b": ["x", "y"]}
    with pytest.raises(ValidationError):
        GetChartDataArgs(chartId="xyz/../1")
