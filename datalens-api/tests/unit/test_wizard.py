import json

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

US_HOST = "http://us.example:8080"
CHART_ID = "4znp91bb2bmin"
WORKBOOK_ID = "pk8aul3ruj188"
REV_ID = "50oqa2cc3cnko"

CREATE_ARGS = {
    "workbookId": WORKBOOK_ID,
    "name": "demo-wizard",
    "template": "datalens",
    "data": {"shared": {"title": "demo"}},
}

US_ENTRY = {
    "entryId": CHART_ID,
    "scope": "widget",
    "type": "graph_wizard_node",
    "key": f"{WORKBOOK_ID}/demo-wizard",
    "unversionedData": {},
    "createdBy": "uid:systemId",
    "createdAt": "2026-08-14T16:14:25.211Z",
    "updatedBy": "uid:systemId",
    "updatedAt": "2026-08-14T16:14:25.211Z",
    "savedId": REV_ID,
    "publishedId": None,
    "revId": REV_ID,
    "tenantId": "common",
    "data": {"shared": {"title": "demo"}},
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

US_PUBLISHED = {**US_ENTRY, "publishedId": REV_ID}

US_DELETE = {
    **US_ENTRY,
    "isDeleted": True,
    "deletedAt": "2026-08-14T16:14:25.300Z",
    "key": f"__trash/{WORKBOOK_ID}_demo-wizard",
}


def _mock_create_then_publish(create_entry: dict, published: dict | None = None):
    create_route = respx.post(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(200, json=create_entry)
    )
    pub = published or {**create_entry, "publishedId": create_entry.get("savedId") or REV_ID}
    publish_route = respx.post(
        f"{US_HOST}/private/entries/{create_entry['entryId']}"
    ).mock(return_value=httpx.Response(200, json=pub))
    return create_route, publish_route


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
def test_create_wizard_chart_posts_widget_entry():
    create_route, publish_route = _mock_create_then_publish(US_ENTRY, US_PUBLISHED)
    response = _rpc("createWizardChart", CREATE_ARGS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entryId"] == CHART_ID
    assert body["scope"] == "widget"
    assert body["type"] == "graph_wizard_node"
    assert body["data"] == {"shared": {"title": "demo"}}
    assert body["publishedId"] == REV_ID
    assert "unversionedData" not in body
    assert "mirrored" not in body
    assert create_route.called
    sent = json.loads(create_route.calls[0].request.content)
    assert sent["scope"] == "widget"
    assert sent["type"] == "graph_wizard_node"
    assert sent["workbookId"] == WORKBOOK_ID
    assert sent["name"] == "demo-wizard"
    assert isinstance(sent["data"]["shared"], str)
    assert json.loads(sent["data"]["shared"]) == {"title": "demo"}
    assert publish_route.called
    published = json.loads(publish_route.calls[0].request.content)
    assert published["mode"] == "publish"
    assert published["data"] == sent["data"]


@respx.mock
def test_get_wizard_chart_returns_entry():
    route = respx.get(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    response = _rpc("getWizardChart", {"chartId": CHART_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entryId"] == CHART_ID
    assert body["type"] == "graph_wizard_node"
    assert "includePermissionsInfo" not in str(route.calls[0].request.url)


@respx.mock
def test_get_wizard_chart_forwards_include_flags():
    route = respx.get(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                **US_ENTRY,
                "permissions": {
                    "execute": True,
                    "read": True,
                    "edit": True,
                    "admin": True,
                },
            },
        )
    )
    response = _rpc(
        "getWizardChart",
        {
            "chartId": CHART_ID,
            "includePermissions": True,
            "includeLinks": True,
            "revId": REV_ID,
            "branch": "saved",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["permissions"] == {
        "execute": True,
        "read": True,
        "edit": True,
        "admin": True,
    }
    params = dict(route.calls[0].request.url.params)
    assert params["includePermissionsInfo"] == "true"
    assert params["includeLinks"] == "true"
    assert params["revId"] == REV_ID
    assert params["branch"] == "saved"


def _table_shared(vis_id: str = "flatTable") -> dict:
    return {
        "title": "demo-table",
        "visualization": {"id": vis_id, "type": "table"},
    }


@respx.mock
def test_create_wizard_chart_derives_table_type_from_flat_table():
    table_entry = {**US_ENTRY, "type": "table_wizard_node", "data": {"shared": _table_shared()}}
    route, _publish = _mock_create_then_publish(table_entry)
    response = _rpc(
        "createWizardChart",
        {
            "workbookId": WORKBOOK_ID,
            "name": "demo-table",
            "template": "datalens",
            "data": {"shared": _table_shared()},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["type"] == "table_wizard_node"
    sent = json.loads(route.calls[0].request.content)
    assert sent["type"] == "table_wizard_node"
    assert isinstance(sent["data"]["shared"], str)
    assert json.loads(sent["data"]["shared"])["visualization"]["id"] == "flatTable"


@respx.mock
def test_create_wizard_chart_accepts_table_alias():
    table_entry = {**US_ENTRY, "type": "table_wizard_node"}
    route, _publish = _mock_create_then_publish(table_entry)
    response = _rpc(
        "createWizardChart",
        {
            "workbookId": WORKBOOK_ID,
            "name": "demo-table-alias",
            "template": "datalens",
            "data": {"shared": _table_shared("table")},
        },
    )
    assert response.status_code == 200, response.text
    sent = json.loads(route.calls[0].request.content)
    assert sent["type"] == "table_wizard_node"
    assert isinstance(sent["data"]["shared"], str)


@respx.mock
def test_create_wizard_chart_keeps_shared_json_string():
    already = json.dumps({"title": "as-string"}, ensure_ascii=False)
    route, _publish = _mock_create_then_publish(US_ENTRY)
    response = _rpc(
        "createWizardChart",
        {
            "workbookId": WORKBOOK_ID,
            "name": "demo-string-shared",
            "template": "datalens",
            "data": {"shared": already},
        },
    )
    assert response.status_code == 200, response.text
    sent = json.loads(route.calls[0].request.content)
    assert sent["data"]["shared"] == already


@respx.mock
def test_update_wizard_chart_posts_mode_and_data():
    updated = {**US_ENTRY, "data": {"shared": {"title": "upd"}}}
    respx.get(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    route = respx.post(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=updated)
    )
    response = _rpc(
        "updateWizardChart",
        {
            "entryId": CHART_ID,
            "template": "datalens",
            "mode": "publish",
            "data": {"shared": {"title": "upd"}},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["entryId"] == CHART_ID
    sent = json.loads(route.calls[0].request.content)
    assert sent["mode"] == "publish"
    assert isinstance(sent["data"]["shared"], str)
    assert json.loads(sent["data"]["shared"]) == {"title": "upd"}
    assert "type" not in sent


@respx.mock
def test_update_wizard_chart_rejects_table_vis_on_graph_entry():
    respx.get(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    post_route = respx.post(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_ENTRY)
    )
    response = _rpc(
        "updateWizardChart",
        {
            "entryId": CHART_ID,
            "template": "datalens",
            "mode": "publish",
            "data": {"shared": _table_shared()},
        },
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "INVALID_ARGUMENT"
    assert "flatTable" in body["message"]
    assert "graph_wizard_node" in body["message"]
    assert not post_route.called


@respx.mock
def test_update_wizard_chart_rejects_line_vis_on_table_entry():
    table_entry = {**US_ENTRY, "type": "table_wizard_node"}
    respx.get(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=table_entry)
    )
    post_route = respx.post(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=table_entry)
    )
    response = _rpc(
        "updateWizardChart",
        {
            "entryId": CHART_ID,
            "template": "datalens",
            "mode": "publish",
            "data": {"shared": {"visualization": {"id": "line"}}},
        },
    )
    assert response.status_code == 400, response.text
    assert "line" in response.json()["message"]
    assert not post_route.called


@respx.mock
def test_delete_wizard_chart_returns_empty_object():
    route = respx.delete(f"{US_HOST}/private/entries/{CHART_ID}").mock(
        return_value=httpx.Response(200, json=US_DELETE)
    )
    response = _rpc("deleteWizardChart", {"chartId": CHART_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {}
    assert route.called


def test_json_lists_wizard_methods():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    for name in (
        "createWizardChart",
        "getWizardChart",
        "updateWizardChart",
        "deleteWizardChart",
    ):
        assert f"/rpc/{name}" in paths
    assert "/rpc/createEditorChart" not in paths
