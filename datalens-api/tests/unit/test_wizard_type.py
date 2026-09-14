import json

import pytest

from app.errors import ApiError
from app.wizard_type import (
    GRAPH_ENTRY_TYPE,
    TABLE_ENTRY_TYPE,
    assert_wizard_type_compatible,
    encode_chart_data_for_us,
    extract_visualization_id,
    resolve_wizard_entry_type,
)


def test_extract_visualization_id_from_object():
    data = {"shared": {"visualization": {"id": "flatTable"}}}
    assert extract_visualization_id(data) == "flatTable"


def test_extract_visualization_id_from_json_string():
    data = {"shared": json.dumps({"visualization": {"id": "pivotTable"}})}
    assert extract_visualization_id(data) == "pivotTable"


def test_extract_visualization_id_missing():
    assert extract_visualization_id({"shared": {"title": "demo"}}) is None
    assert extract_visualization_id({}) is None
    assert extract_visualization_id(None) is None


@pytest.mark.parametrize(
    ("vis_id", "expected"),
    [
        (None, GRAPH_ENTRY_TYPE),
        ("line", GRAPH_ENTRY_TYPE),
        ("metric", GRAPH_ENTRY_TYPE),
        ("flatTable", TABLE_ENTRY_TYPE),
        ("pivotTable", TABLE_ENTRY_TYPE),
        ("table", TABLE_ENTRY_TYPE),
    ],
)
def test_resolve_wizard_entry_type(vis_id, expected):
    shared: dict = {"title": "demo"}
    if vis_id is not None:
        shared["visualization"] = {"id": vis_id}
    assert resolve_wizard_entry_type({"shared": shared}) == expected


def test_assert_compatible_when_visualization_absent():
    assert_wizard_type_compatible(GRAPH_ENTRY_TYPE, {"shared": {"title": "demo"}})
    assert_wizard_type_compatible(TABLE_ENTRY_TYPE, {"shared": {"title": "demo"}})


def test_assert_rejects_table_vis_on_graph_entry():
    with pytest.raises(ApiError) as exc:
        assert_wizard_type_compatible(
            GRAPH_ENTRY_TYPE,
            {"shared": {"visualization": {"id": "flatTable"}}},
        )
    assert exc.value.status_code == 400
    assert exc.value.code == "INVALID_ARGUMENT"
    assert "flatTable" in exc.value.message
    assert GRAPH_ENTRY_TYPE in exc.value.message
    assert TABLE_ENTRY_TYPE in exc.value.message


def test_assert_rejects_line_vis_on_table_entry():
    with pytest.raises(ApiError) as exc:
        assert_wizard_type_compatible(
            TABLE_ENTRY_TYPE,
            {"shared": {"visualization": {"id": "line"}}},
        )
    assert exc.value.status_code == 400
    assert "line" in exc.value.message
    assert TABLE_ENTRY_TYPE in exc.value.message
    assert GRAPH_ENTRY_TYPE in exc.value.message


def test_assert_allows_matching_families():
    assert_wizard_type_compatible(
        GRAPH_ENTRY_TYPE,
        {"shared": {"visualization": {"id": "line"}}},
    )
    assert_wizard_type_compatible(
        TABLE_ENTRY_TYPE,
        {"shared": {"visualization": {"id": "flatTable"}}},
    )


def test_encode_chart_data_for_us_stringifies_shared_object():
    data = {"shared": {"title": "демо", "visualization": {"id": "flatTable"}}}
    encoded = encode_chart_data_for_us(data)
    assert isinstance(encoded["shared"], str)
    assert json.loads(encoded["shared"]) == data["shared"]
    assert data["shared"] == {"title": "демо", "visualization": {"id": "flatTable"}}


def test_encode_chart_data_for_us_keeps_existing_string():
    raw = json.dumps({"title": "already"}, ensure_ascii=False)
    encoded = encode_chart_data_for_us({"shared": raw})
    assert encoded["shared"] == raw


def test_encode_chart_data_for_us_passthrough_without_shared():
    assert encode_chart_data_for_us({"other": 1}) == {"other": 1}
    assert encode_chart_data_for_us(None) is None
