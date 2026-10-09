import json

from app.tools.compact import compact_chart, compact_dashboard, compact_dataset, compact_entries

DASHBOARD = {
    "entry": {
        "entryId": "d1",
        "key": "123/Продажи",
        "workbookId": "wb1",
        "annotation": {"description": "Главный"},
        "data": {
            "tabs": [
                {
                    "id": "t1",
                    "title": "Обзор",
                    "items": [
                        {"type": "widget", "data": {"tabs": [{"title": "Выручка", "chartId": "c1", "params": {}}, {"title": "Без чарта"}]}},
                        {
                            "type": "group_control",
                            "data": {
                                "group": [
                                    {"title": "Дата", "defaults": {"Дата": "__interval"}, "sourceType": "manual", "source": {"fieldName": "Дата"}},
                                    {"title": "ТН", "defaults": {"tn": []}, "sourceType": "dataset", "source": {"datasetId": "ds1", "datasetFieldId": "f1"}},
                                ]
                            },
                        },
                        {"type": "control", "data": {"title": "Канал", "defaults": {"ch": ""}, "sourceType": "dataset", "source": {"datasetId": "ds1", "datasetFieldId": "f2"}}},
                        {"type": "title", "data": {"text": "Заголовок"}},
                    ],
                }
            ]
        },
    }
}


def test_compact_dashboard():
    assert compact_dashboard(DASHBOARD) == {
        "dashboardId": "d1",
        "title": "Продажи",
        "workbookId": "wb1",
        "description": "Главный",
        "tabs": [
            {
                "id": "t1",
                "title": "Обзор",
                "charts": [{"title": "Выручка", "chartId": "c1", "params": {}}],
                "selectors": [
                    {"title": "Дата", "params": ["Дата"], "sourceType": "manual", "datasetId": None, "fieldId": "Дата"},
                    {"title": "ТН", "params": ["tn"], "sourceType": "dataset", "datasetId": "ds1", "fieldId": "f1"},
                    {"title": "Канал", "params": ["ch"], "sourceType": "dataset", "datasetId": "ds1", "fieldId": "f2"},
                ],
                "texts": ["Заголовок"],
            }
        ],
    }


def test_compact_wizard_chart():
    shared = {
        "datasetsIds": ["ds1"],
        "visualization": {
            "id": "line",
            "layers": [
                {
                    "id": "layer-1",
                    "commonPlaceholders": {"filters": []},
                    "placeholders": [
                        {"id": "x", "items": [{"title": "Дата", "guid": "g1"}]},
                        {"id": "y", "items": [{"title": "Выручка"}, {"title": "Выручка"}]},
                        {"id": "colors", "items": []},
                    ],
                }
            ],
        },
        "filters": [{"title": "Канал", "filter": {"operation": {"code": "IN"}, "value": ["WB"]}}],
        "colors": [{"title": "Канал"}],
        "sort": [],
    }
    body = {"entryId": "c1", "key": "9/Выручка по дням", "type": "graph_wizard_node", "workbookId": "wb1", "data": {"shared": json.dumps(shared)}}
    assert compact_chart(body, "wizard") == {
        "chartId": "c1",
        "title": "Выручка по дням",
        "kind": "wizard",
        "type": "graph_wizard_node",
        "workbookId": "wb1",
        "visualization": "line",
        "datasetIds": ["ds1"],
        "placeholders": {"x": ["Дата"], "y": ["Выручка"]},
        "filters": [{"field": "Канал", "operation": {"code": "IN"}, "value": ["WB"]}],
        "colors": ["Канал"],
        "sort": [],
    }


def test_compact_ql_chart():
    shared = {"queryValue": "SELECT 1", "params": [{"name": "from"}], "visualization": {"id": "table", "placeholders": [{"id": "columns", "items": [{"title": "name"}]}]}}
    body = {"entryId": "q1", "key": "9/Размеры", "type": "table_ql_node", "workbookId": "wb1", "data": {"shared": json.dumps(shared)}}
    assert compact_chart(body, "ql") == {
        "chartId": "q1",
        "title": "Размеры",
        "kind": "ql",
        "type": "table_ql_node",
        "workbookId": "wb1",
        "visualization": "table",
        "query": "SELECT 1",
        "params": ["from"],
        "placeholders": {"columns": ["name"]},
    }


def test_compact_dataset_skips_hidden_fields():
    body = {
        "id": "ds1",
        "key": "7/Продажи",
        "name": "Продажи",
        "workbook_id": "wb1",
        "dataset": {
            "description": "",
            "result_schema": [
                {"title": "Дата", "guid": "dt", "type": "DIMENSION", "data_type": "date", "aggregation": "none", "description": "День заказа", "calc_mode": "direct"},
                {"title": "Скрытое", "guid": "h", "hidden": True},
                {"title": "Маржа", "guid": "m", "type": "MEASURE", "data_type": "float", "aggregation": "sum", "description": "", "calc_mode": "formula"},
            ],
            "sources": [{"title": "orders"}],
        },
    }
    assert compact_dataset(body) == {
        "datasetId": "ds1",
        "title": "Продажи",
        "workbookId": "wb1",
        "description": "",
        "fields": [
            {"title": "Дата", "guid": "dt", "type": "DIMENSION", "dataType": "date", "aggregation": "none", "description": "День заказа"},
            {"title": "Маржа", "guid": "m", "type": "MEASURE", "dataType": "float", "aggregation": "sum", "calculated": True},
        ],
        "sources": ["orders"],
    }


def test_compact_entries():
    body = {"entries": [{"entryId": "c1", "scope": "widget", "type": "graph_wizard_node", "key": "1/Папка/Чарт", "workbookId": "wb1"}, "junk"], "nextPageToken": "2"}
    assert compact_entries(body) == {
        "entries": [{"entryId": "c1", "scope": "widget", "type": "graph_wizard_node", "title": "Чарт"}],
        "count": 1,
        "nextPageToken": "2",
    }


def test_odd_shapes_do_not_crash():
    assert compact_dashboard({})["tabs"] == []
    assert compact_dashboard({"entry": {"data": {"tabs": [None, {"items": None}]}}})["tabs"][0]["charts"] == []
    assert compact_chart({"data": {"shared": "{broken"}}, "wizard")["placeholders"] == {}
    assert compact_chart({}, "ql")["query"] == ""
    assert compact_dataset({"dataset": None})["fields"] == []
    assert compact_entries({"entries": None})["count"] == 0
