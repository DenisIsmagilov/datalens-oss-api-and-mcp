import json
import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import create_app

AUTH = "http://auth.example:8080"
DATA = "http://data-api.example:8080"
UI = "http://ui.example:8080"
DS = "ds123"

SCHEMA = {
    "fields": [
        {"title": "Город", "guid": "city", "type": "DIMENSION", "data_type": "string"},
        {"title": "Выручка", "guid": "rev", "type": "MEASURE", "data_type": "float"},
        {"title": "Дата", "guid": "dt", "type": "DIMENSION", "data_type": "date"},
    ]
}


def _row_field(title, guid, legend, data_type, role="row"):
    return {"title": title, "id": guid, "legend_item_id": legend, "data_type": data_type, "role_spec": {"role": role}}


def _mock_common():
    respx.post(f"{AUTH}/signin").mock(return_value=httpx.Response(200, json={"accessToken": "jwt"}))
    respx.get(f"{DATA}/api/data/v2/datasets/{DS}/fields").mock(
        return_value=httpx.Response(200, json=SCHEMA)
    )


def _rpc(method: str, payload: dict) -> httpx.Response:
    return TestClient(create_app()).post(
        f"/rpc/{method}", json=payload, headers={"Authorization": "Bearer test-dl-api-token"}
    )


@respx.mock
def test_query_dataset_end_to_end(caplog):
    _mock_common()
    route = respx.post(f"{DATA}/api/data/v2/datasets/{DS}/result").mock(
        return_value=httpx.Response(
            200,
            json={
                "result_data": [{"rows": [
                    {"data": ["Москва", "10.5"], "legend": [0, 1]},
                    {"data": ["Казань", "3"], "legend": [0, 1]},
                ]}],
                "fields": [_row_field("Город", "city", 0, "string"), _row_field("Выручка", "rev", 1, "float")],
                "blocks": [{"block_id": 0, "query": "SELECT secret"}],
            },
        )
    )
    with caplog.at_level(logging.INFO, logger="datalens_api.data"):
        response = _rpc(
            "queryDataset",
            {
                "datasetId": DS,
                "fields": ["Город", "Выручка"],
                "filters": [{"field": "Город", "op": "in", "values": ["Москва-секрет"]}],
                "limit": 1,
            },
        )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "columns": [{"title": "Город", "dataType": "string"}, {"title": "Выручка", "dataType": "float"}],
        "rows": [["Москва", 10.5]],
        "rowCount": 1,
        "truncated": True,
    }
    sent = json.loads(route.calls[0].request.content)
    assert sent["limit"] == 2
    assert sent["filters"][0]["operation"] == "IN"
    assert "SELECT" not in response.text
    log_text = caplog.text
    assert "queryDataset" in log_text and "status=OK" in log_text
    assert "backendStatus=200" in log_text
    assert "Москва" not in log_text
    assert "jwt" not in log_text


@respx.mock
def test_query_dataset_backend_error_is_logged_with_backend_status(caplog):
    _mock_common()
    respx.post(f"{DATA}/api/data/v2/datasets/{DS}/result").mock(
        return_value=httpx.Response(
            500, json={"code": "ERR.DS_API.DB", "message": "boom", "debug": {"query": "SELECT 1"}}
        )
    )
    with caplog.at_level(logging.INFO, logger="datalens_api.data"):
        response = _rpc("queryDataset", {"datasetId": DS, "fields": ["Город"]})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert response.json().get("details", {}) == {}
    assert "SELECT" not in response.text
    assert "status=INTERNAL" in caplog.text and "backendStatus=500" in caplog.text


@respx.mock
def test_query_dataset_unexpected_error_is_logged(caplog, monkeypatch):
    _mock_common()
    respx.post(f"{DATA}/api/data/v2/datasets/{DS}/result").mock(
        return_value=httpx.Response(200, json={"result_data": []})
    )

    def _broken(*_args, **_kwargs):
        raise KeyError("fields")

    monkeypatch.setattr("app.methods.data.parse_result", _broken)
    with caplog.at_level(logging.INFO, logger="datalens_api.data"):
        response = _rpc("queryDataset", {"datasetId": DS, "fields": ["Город"]})
    assert response.status_code == 500
    assert "method=queryDataset" in caplog.text and "status=INTERNAL" in caplog.text


@pytest.mark.parametrize(
    "bad_filter",
    [
        {"field": "Дата", "op": "between", "values": ["2026-01-01-секрет"]},
        {"field": "Город", "op": "in", "values": []},
        {"field": "Город", "op": "isnull", "values": ["x"]},
    ],
)
def test_query_dataset_bad_filter_values_is_400_without_echo(bad_filter):
    response = _rpc("queryDataset", {"datasetId": DS, "fields": ["Город"], "filters": [bad_filter]})
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_ARGUMENT"
    assert "секрет" not in response.text
    assert "ValueError" not in response.text


@respx.mock
def test_query_dataset_db_error_message_is_generic():
    _mock_common()
    respx.post(f"{DATA}/api/data/v2/datasets/{DS}/result").mock(
        return_value=httpx.Response(
            400, json={"code": "ERR.DS_API.DB.SOURCE_ERROR", "message": "Invalid object name 'dbo.secret_table'"}
        )
    )
    response = _rpc("queryDataset", {"datasetId": DS, "fields": ["Город"]})
    assert response.status_code == 400
    assert response.json()["details"] == {"code": "ERR.DS_API.DB.SOURCE_ERROR"}
    assert "secret_table" not in response.text


@respx.mock
def test_field_values_distinct_without_distinct_column_is_empty():
    _mock_common()
    respx.post(f"{DATA}/api/data/v2/datasets/{DS}/values/distinct").mock(
        return_value=httpx.Response(
            200,
            json={"result_data": [{"rows": [{"data": [], "legend": []}]}], "fields": []},
        )
    )
    response = _rpc("getDatasetFieldValues", {"datasetId": DS, "field": "Город"})
    assert response.status_code == 200, response.text
    assert response.json()["values"] == []


@respx.mock
def test_query_dataset_limit_above_max_is_400():
    response = _rpc("queryDataset", {"datasetId": DS, "fields": ["Город"], "limit": 501})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_ARGUMENT"


@respx.mock
def test_query_dataset_unknown_field_lists_available():
    _mock_common()
    response = _rpc("queryDataset", {"datasetId": DS, "fields": ["Нет такого"]})
    assert response.status_code == 400
    assert response.json()["details"]["availableFields"] == ["Город", "Выручка", "Дата"]


@respx.mock
def test_field_values_distinct():
    _mock_common()
    route = respx.post(f"{DATA}/api/data/v2/datasets/{DS}/values/distinct").mock(
        return_value=httpx.Response(
            200,
            json={
                "result_data": [{"rows": [{"data": ["Москва"], "legend": [0]}]}],
                "fields": [_row_field("Город", "city", 0, "string", role="distinct"), _row_field("Город", "city", 1, "string", role="filter")],
            },
        )
    )
    response = _rpc("getDatasetFieldValues", {"datasetId": DS, "field": "Город", "search": "моск"})
    assert response.status_code == 200, response.text
    assert response.json() == {"field": "Город", "values": ["Москва"], "truncated": False}
    sent = json.loads(route.calls[0].request.content)
    assert sent["filters"] == [{"ref": {"type": "id", "id": "city"}, "operation": "ICONTAINS", "values": ["моск"]}]


@respx.mock
def test_field_values_distinct_limit_above_max_is_400():
    response = _rpc("getDatasetFieldValues", {"datasetId": DS, "field": "Город", "limit": 201})
    assert response.status_code == 400


@respx.mock
def test_field_values_range():
    _mock_common()
    respx.post(f"{DATA}/api/data/v2/datasets/{DS}/result").mock(
        return_value=httpx.Response(
            200,
            json={
                "result_data": [{"rows": [{"data": ["2024-01-01", "2026-10-06"], "legend": [0, 1]}]}],
                "fields": [_row_field("__range_min", "__range_min", 0, "date"), _row_field("__range_max", "__range_max", 1, "date")],
            },
        )
    )
    response = _rpc("getDatasetFieldValues", {"datasetId": DS, "field": "Дата", "mode": "range"})
    assert response.status_code == 200, response.text
    assert response.json() == {"field": "Дата", "min": "2024-01-01", "max": "2026-10-06"}


@respx.mock
def test_get_chart_data_table():
    respx.post(f"{AUTH}/signin").mock(return_value=httpx.Response(200, json={"accessToken": "jwt"}))
    route = respx.post(f"{UI}/api/run").mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "table_wizard_node",
                "key": "1/Продажи",
                "extra": {"datasets": [{"id": "ds123"}]},
                "sources": {"s": {"sql_query": "SELECT secret"}},
                "data": {"head": [{"id": "c", "name": "Город", "type": "text"}], "rows": [{"cells": [{"value": "Москва"}]}]},
            },
        )
    )
    response = _rpc("getChartData", {"chartId": "ch1", "params": {"Город": ["Москва"]}})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "chartId": "ch1",
        "title": "Продажи",
        "visualization": "table",
        "datasetIds": ["ds123"],
        "columns": [{"title": "Город", "dataType": "text"}],
        "rows": [["Москва"]],
        "rowCount": 1,
        "truncated": False,
        "normalized": True,
    }
    assert json.loads(route.calls[0].request.content) == {"id": "ch1", "params": {"Город": ["Москва"]}}
    assert "SELECT" not in response.text


@respx.mock
def test_get_chart_data_unsupported_has_note():
    respx.post(f"{AUTH}/signin").mock(return_value=httpx.Response(200, json={"accessToken": "jwt"}))
    respx.post(f"{UI}/api/run").mock(
        return_value=httpx.Response(200, json={"type": "d3_wizard_node", "key": "1/Доли", "data": {"series": {}}})
    )
    body = _rpc("getChartData", {"chartId": "ch2"}).json()
    assert body["normalized"] is False and body["note"]
