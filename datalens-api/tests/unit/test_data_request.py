import pytest

from app.adapters.data_request import (
    DatasetField,
    build_distinct_body,
    build_range_body,
    build_result_body,
    fields_from_schema,
    resolve_field,
)
from app.errors import ApiError
from app.models.rpc_data import CalculatedField, DataFilter, OrderBy

SCHEMA = {
    "fields": [
        {"title": "Город", "guid": "city", "type": "DIMENSION", "data_type": "string"},
        {"title": "Выручка", "guid": "rev", "type": "MEASURE", "data_type": "float"},
        {"title": "Дата", "guid": "dt", "type": "DIMENSION", "data_type": "date"},
        {"title": "Дубль", "guid": "d1", "type": "DIMENSION", "data_type": "string"},
        {"title": "Дубль", "guid": "d2", "type": "DIMENSION", "data_type": "string"},
    ],
    "revision_id": "r",
}
FIELDS = fields_from_schema(SCHEMA)


def _ref(guid: str) -> dict:
    return {"type": "id", "id": guid}


def test_fields_from_schema():
    assert FIELDS[0] == DatasetField(guid="city", title="Город", data_type="string")
    assert len(FIELDS) == 5


def test_resolve_by_title_and_guid():
    assert resolve_field("Город", FIELDS).guid == "city"
    assert resolve_field("rev", FIELDS).title == "Выручка"


def test_resolve_unknown_lists_available():
    with pytest.raises(ApiError) as exc:
        resolve_field("Нет", FIELDS)
    assert exc.value.code == "INVALID_ARGUMENT"
    assert exc.value.details["field"] == "Нет"
    assert "Город" in exc.value.details["availableFields"]


def test_resolve_ambiguous_lists_candidates():
    with pytest.raises(ApiError) as exc:
        resolve_field("Дубль", FIELDS)
    assert {c["guid"] for c in exc.value.details["candidates"]} == {"d1", "d2"}


def test_result_body_full():
    body = build_result_body(
        fields=["Город", "Средний чек"],
        calculated=[CalculatedField(title="Средний чек", formula="SUM([Выручка]) / 2")],
        filters=[
            DataFilter(field="Дата", op="between", values=["2026-09-01", "2026-09-30"]),
            DataFilter(field="Город", op="in", values=["Москва", 1, True]),
            DataFilter(field="Средний чек", op="isnotnull"),
        ],
        order_by=[OrderBy(field="Средний чек", direction="desc")],
        dataset_fields=FIELDS,
        limit=50,
    )
    assert body["limit"] == 51
    assert body["fields"] == [{"ref": _ref("city")}, {"ref": _ref("__calc_0")}]
    assert body["updates"] == [
        {
            "action": "add_field",
            "field": {
                "guid": "__calc_0",
                "title": "Средний чек",
                "calc_mode": "formula",
                "formula": "SUM([Выручка]) / 2",
            },
        }
    ]
    assert body["filters"] == [
        {"ref": _ref("dt"), "operation": "BETWEEN", "values": ["2026-09-01", "2026-09-30"]},
        {"ref": _ref("city"), "operation": "IN", "values": ["Москва", "1", "true"]},
        {"ref": _ref("__calc_0"), "operation": "ISNOTNULL", "values": []},
    ]
    assert body["order_by"] == [{"ref": _ref("__calc_0"), "direction": "desc"}]


def test_result_body_minimal_has_no_optional_keys():
    body = build_result_body(
        fields=["Город"], calculated=[], filters=[], order_by=[], dataset_fields=FIELDS, limit=1
    )
    assert set(body) == {"fields", "limit"}


@pytest.mark.parametrize("formula", ["DB_CALL_INT('x', [Город])", "1 + db_call_text('y')"])
def test_db_call_rejected(formula):
    with pytest.raises(ApiError) as exc:
        build_result_body(
            fields=["c"],
            calculated=[CalculatedField(title="c", formula=formula)],
            filters=[],
            order_by=[],
            dataset_fields=FIELDS,
            limit=1,
        )
    assert exc.value.details == {"formulaTitle": "c"}


def test_calculated_title_conflict_rejected():
    with pytest.raises(ApiError) as exc:
        build_result_body(
            fields=["Город"],
            calculated=[CalculatedField(title="Город", formula="1")],
            filters=[],
            order_by=[],
            dataset_fields=FIELDS,
            limit=1,
        )
    assert exc.value.code == "INVALID_ARGUMENT"


def test_distinct_body_with_search():
    body, target = build_distinct_body(
        field="Город",
        search="моск",
        filters=[DataFilter(field="Дата", op="gte", values=["2026-01-01"])],
        dataset_fields=FIELDS,
        limit=100,
    )
    assert target.guid == "city"
    assert body == {
        "fields": [{"ref": _ref("city"), "role_spec": {"role": "distinct"}}],
        "filters": [
            {"ref": _ref("dt"), "operation": "GTE", "values": ["2026-01-01"]},
            {"ref": _ref("city"), "operation": "ICONTAINS", "values": ["моск"]},
        ],
        "limit": 101,
    }


def test_range_body_uses_min_max_formulas():
    body, target = build_range_body(field="dt", filters=[], dataset_fields=FIELDS)
    assert target.title == "Дата"
    assert body["fields"] == [{"ref": _ref("__range_min")}, {"ref": _ref("__range_max")}]
    assert [u["field"]["formula"] for u in body["updates"]] == ["MIN([Дата])", "MAX([Дата])"]
    assert body["limit"] == 1


def test_range_formula_escapes_brackets():
    fields = [DatasetField(guid="g", title="a]b\\c", data_type="string")]
    body, _ = build_range_body(field="g", filters=[], dataset_fields=fields)
    assert body["updates"][0]["field"]["formula"] == "MIN([a\\]b\\\\c])"
