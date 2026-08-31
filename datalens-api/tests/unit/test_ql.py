import json

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

US_HOST = "http://us.example:8080"
CHART_ID = "qlchartqlchart"
WORKBOOK_ID = "pk8aul3ruj188"
REV_ID = "qlrevqlrevql1"

CREATE_ARGS = {
    "workbookId": WORKBOOK_ID,
    "name": "demo-ql",
    "template": "ql",
    "data": {"shared": {"title": "demo-ql"}},
}

US_ENTRY = {
    "entryId": CHART_ID,
    "scope": "widget",
    "type": "ql",
    "key": f"{WORKBOOK_ID}/demo-ql",
    "unversionedData": {},
    "createdBy": "uid:systemId",
    "createdAt": "2026-08-14T16:14:25.400Z",
    "updatedBy": "uid:systemId",
    "updatedAt": "2026-08-14T16:14:25.400Z",
    "savedId": REV_ID,
    "publishedId": None,
    "revId": REV_ID,
    "tenantId": "common",
    "data": {"shared": {"title": "demo-ql"}},
    "meta": {},
    "annotation": None,
    "hidden": False,
    "mirrored": False,
    "public": False,
    "workbookId": WORKBOOK_ID,
    "collectionId": None,
    "version": None,
    "sourceVersion": None,
    "links": None,
}


def _rpc(method: str, payload: dict) -> httpx.Response:
    client = TestClient(create_app())
    return client.post(
        f"/rpc/{method}",
        json=payload,
        headers={
            "Authorization": "Bearer test-dl-api-token",
            "x-dl-api-version": "2",
        },
    )


@respx.mock
def test_create_ql_chart_posts_widget_entry():
    route = respx.post(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    response = _rpc("createQLChart", CREATE_ARGS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entryId"] == CHART_ID
    assert body["type"] == "ql"
    assert "unversionedData" not in body
    sent = json.loads(route.calls[0].request.content)
    assert sent["scope"] == "widget"
    assert sent["type"] == "ql"
    assert sent["name"] == "demo-ql"


@respx.mock
def test_get_ql_chart_returns_entry():
    respx.get(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    response = _rpc("getQLChart", {"chartId": CHART_ID})
    assert response.status_code == 200, response.text
    assert response.json()["entryId"] == CHART_ID


@respx.mock
def test_update_ql_chart_posts_mode_and_data():
    route = respx.post(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    response = _rpc(
        "updateQLChart",
        {
            "entryId": CHART_ID,
            "template": "ql",
            "mode": "save",
            "data": {"shared": {"title": "upd"}},
        },
    )
    assert response.status_code == 200, response.text
    sent = json.loads(route.calls[0].request.content)
    assert sent["mode"] == "save"
    assert sent["data"] == {"shared": {"title": "upd"}}


@respx.mock
def test_delete_ql_chart_returns_empty_object():
    respx.delete(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json={**US_ENTRY, "isDeleted": True})
    )
    response = _rpc("deleteQLChart", {"chartId": CHART_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {}


def test_json_lists_ql_and_not_editor():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    for name in (
        "createDashboard",
        "getDashboard",
        "updateDashboard",
        "deleteDashboard",
        "createWizardChart",
        "getWizardChart",
        "updateWizardChart",
        "deleteWizardChart",
        "createQLChart",
        "getQLChart",
        "updateQLChart",
        "deleteQLChart",
    ):
        assert f"/rpc/{name}" in paths
    assert "/rpc/createEditorChart" not in paths
