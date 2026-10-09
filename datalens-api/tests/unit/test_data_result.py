from app.adapters.data_result import cast_value, clip, parse_result

RESULT = {
    "result_data": [
        {
            "rows": [
                {"data": ["Москва", "9", "3.5", "2026-09-01"], "legend": [0, 1, 2, 3]},
                {"data": [None, "4", "1.0", None], "legend": [0, 1, 2, 3]},
                {"data": ["Казань", "1", "0.5", "2026-09-02"], "legend": [0, 1, 2, 3]},
            ]
        }
    ],
    "fields": [
        {"title": "Город", "id": "city", "legend_item_id": 0, "data_type": "string", "role_spec": {"role": "row", "visibility": "visible"}},
        {"title": "cnt", "id": "__calc_0", "legend_item_id": 1, "data_type": "integer", "role_spec": {"role": "row", "visibility": "visible"}},
        {"title": "avg", "id": "__calc_1", "legend_item_id": 2, "data_type": "float", "role_spec": {"role": "row", "visibility": "visible"}},
        {"title": "Дата", "id": "dt", "legend_item_id": 3, "data_type": "date", "role_spec": {"role": "row", "visibility": "visible"}},
        {"title": "cnt", "id": "__calc_0", "legend_item_id": 4, "data_type": "integer", "role_spec": {"role": "order_by", "direction": "desc"}},
        {"title": "Город", "id": "city", "legend_item_id": 5, "data_type": "string", "role_spec": {"role": "filter"}},
    ],
    "blocks": [{"block_id": 0, "query": "SELECT secret FROM t"}],
}


def test_only_row_role_columns_and_casting():
    columns, rows, truncated = parse_result(RESULT, role="row", limit=10, max_chars=500)
    assert [(c.title, c.dataType) for c in columns] == [
        ("Город", "string"),
        ("cnt", "integer"),
        ("avg", "float"),
        ("Дата", "date"),
    ]
    assert rows[0] == ["Москва", 9, 3.5, "2026-09-01"]
    assert rows[1] == [None, 4, 1.0, None]
    assert truncated is False


def test_truncation_by_limit_plus_one():
    _, rows, truncated = parse_result(RESULT, role="row", limit=2, max_chars=500)
    assert len(rows) == 2 and truncated is True


def test_distinct_role():
    body = {
        "result_data": [{"rows": [{"data": ["a"], "legend": [0]}, {"data": ["b"], "legend": [0]}]}],
        "fields": [
            {"title": "Склад", "id": "s", "legend_item_id": 0, "data_type": "string", "role_spec": {"role": "distinct"}},
            {"title": "Склад", "id": "s", "legend_item_id": 1, "data_type": "string", "role_spec": {"role": "filter"}},
        ],
    }
    columns, rows, _ = parse_result(body, role="distinct", limit=10, max_chars=500)
    assert [c.title for c in columns] == ["Склад"]
    assert rows == [["a"], ["b"]]


def test_empty_result():
    columns, rows, truncated = parse_result(
        {"result_data": [{"rows": []}], "fields": RESULT["fields"]}, role="row", limit=5, max_chars=500
    )
    assert len(columns) == 4 and rows == [] and truncated is False


def test_cast_fallbacks_and_clip():
    assert cast_value("x", "integer", 500) == "x"
    assert cast_value("true", "boolean", 500) is True
    assert cast_value("a" * 10, "string", 4) == "aaaa…"
    assert clip(5, 1) == 5
