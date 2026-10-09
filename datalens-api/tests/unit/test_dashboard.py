import json

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

US_HOST = "http://us.example:8080"
DASH_ID = "ythj3vhvwphmh"
WORKBOOK_ID = "pk8aul3ruj188"
REV_ID = "zuik4wiwxqioi"

MIN_TAB = {
    "id": "t1",
    "title": "Tab",
    "items": [],
    "layout": [],
    "connections": [],
    "aliases": {},
}

MIN_SETTINGS = {
    "silentLoading": False,
    "dependentSelectors": False,
    "expandTOC": False,
    "autoupdateInterval": None,
    "maxConcurrentRequests": None,
}

MIN_DATA = {
    "counter": 1,
    "salt": "test-salt",
    "schemeVersion": 8,
    "tabs": [MIN_TAB],
    "settings": MIN_SETTINGS,
}

CREATE_ARGS = {
    "entry": {
        "workbookId": WORKBOOK_ID,
        "name": "demo-dash",
        "data": MIN_DATA,
        "meta": {},
    }
}

US_CREATE = {
    "entryId": DASH_ID,
    "scope": "dash",
    "type": "",
    "key": f"{WORKBOOK_ID}/demo-dash",
    "unversionedData": {},
    "createdBy": "uid:systemId",
    "createdAt": "2026-08-14T16:14:25.036Z",
    "updatedBy": "uid:systemId",
    "updatedAt": "2026-08-14T16:14:25.036Z",
    "savedId": REV_ID,
    "publishedId": None,
    "revId": REV_ID,
    "tenantId": "common",
    "data": {
        "salt": "test-salt",
        "tabs": [
            {
                "id": "t1",
                "items": [],
                "title": "Tab",
                "layout": [],
                "aliases": {},
            }
        ],
        "counter": 1,
        "settings": {},
        "schemeVersion": 8,
    },
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

US_GET = {
    "entryId": DASH_ID,
    "scope": "dash",
    "type": "dash",
    "key": f"{WORKBOOK_ID}/demo-dash",
    "createdBy": "uid:systemId",
    "createdAt": "2026-08-14T16:14:25.036Z",
    "updatedBy": "uid:systemId",
    "updatedAt": "2026-08-14T16:14:25.036Z",
    "savedId": REV_ID,
    "publishedId": None,
    "revId": REV_ID,
    "tenantId": "common",
    "data": {
        "salt": "test-salt",
        "tabs": [
            {
                "id": "t1",
                "items": [],
                "title": "Tab",
                "layout": [],
                "aliases": {},
            }
        ],
        "counter": 1,
        "settings": {},
        "schemeVersion": 8,
    },
    "meta": {},
    "annotation": None,
    "version": None,
    "sourceVersion": None,
    "hidden": False,
    "public": False,
    "workbookId": WORKBOOK_ID,
    "collectionId": None,
}

US_GET_PERMS = {
    **US_GET,
    "links": None,
    "permissions": {
        "execute": True,
        "read": True,
        "edit": True,
        "admin": True,
    },
}

US_DELETE = {
    **US_GET,
    "isDeleted": True,
    "deletedAt": "2026-08-14T16:14:25.149Z",
    "key": f"__trash/{WORKBOOK_ID}_demo-dash",
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
def test_create_dashboard_posts_private_entries():
    create_route = respx.post(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(200, json=US_CREATE)
    )
    published = {**US_CREATE, "publishedId": REV_ID}
    publish_route = respx.post(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=published)
    )
    response = _rpc("createDashboard", CREATE_ARGS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "entry" in body
    entry = body["entry"]
    assert entry["entryId"] == DASH_ID
    assert entry["type"] == ""
    assert entry["version"] == 1
    assert entry["createdBy"] == "uid:systemId"
    assert entry["publishedId"] == REV_ID
    assert entry["data"]["settings"]["silentLoading"] is False
    assert entry["data"]["settings"]["dependentSelectors"] is False
    assert entry["data"]["settings"]["expandTOC"] is False
    assert "permissions" not in body
    assert create_route.called
    sent = json.loads(create_route.calls[0].request.content)
    assert sent["scope"] == "dash"
    assert sent["type"] == ""
    assert sent["workbookId"] == WORKBOOK_ID
    assert sent["name"] == "demo-dash"
    assert sent["data"]["schemeVersion"] == 8
    assert publish_route.called
    published_body = json.loads(publish_route.calls[0].request.content)
    assert published_body["mode"] == "publish"
    assert published_body["data"] == sent["data"]
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(body)


@respx.mock
def test_get_dashboard_coerces_us_raw():
    route = respx.get(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=US_GET)
    )
    response = _rpc("getDashboard", {"dashboardId": DASH_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    entry = body["entry"]
    assert entry["entryId"] == DASH_ID
    assert entry["type"] == ""
    assert entry["version"] == 1
    assert entry["createdBy"] == "uid:systemId"
    assert entry["data"]["settings"]["silentLoading"] is False
    assert "permissions" not in body
    assert route.called
    assert "includePermissionsInfo" not in str(route.calls[0].request.url)
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(body)


@respx.mock
def test_get_dashboard_normalizes_recon_scheme_version():
    us_recon = {
        **US_GET,
        "type": "dash",
        "version": None,
        "data": {**US_GET["data"], "schemeVersion": 2},
    }
    respx.get(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=us_recon)
    )
    response = _rpc("getDashboard", {"dashboardId": DASH_ID})
    assert response.status_code == 200, response.text
    entry = response.json()["entry"]
    assert entry["version"] == 1
    assert entry["data"]["schemeVersion"] == 8
    assert entry["type"] == ""
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(response.json())


@respx.mock
def test_get_dashboard_strips_unknown_tab_keys():
    us_rich = {
        **US_GET,
        "type": "dash",
        "version": None,
        "data": {
            **US_GET["data"],
            "schemeVersion": 2,
            "tabs": [
                {
                    "id": "t1",
                    "title": "Tab",
                    "items": [
                        {
                            "id": "i1",
                            "namespace": "default",
                            "type": "text",
                            "data": {"text": "hello"},
                            "unknownItemKey": True,
                        }
                    ],
                    "layout": [],
                    "aliases": {"other": [["x"]]},
                    "foo": 1,
                }
            ],
        },
    }
    respx.get(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=us_rich)
    )
    response = _rpc("getDashboard", {"dashboardId": DASH_ID})
    assert response.status_code == 200, response.text
    entry = response.json()["entry"]
    assert entry["type"] == ""
    assert entry["version"] == 1
    assert entry["data"]["schemeVersion"] == 8
    tab = entry["data"]["tabs"][0]
    assert "foo" not in tab
    assert tab["aliases"] == {}
    assert "unknownItemKey" not in tab["items"][0]
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(response.json())


@respx.mock
def test_get_dashboard_fills_group_control_show_group_name():
    us_group = {
        **US_GET,
        "data": {
            **US_GET["data"],
            "tabs": [
                {
                    "id": "t1",
                    "title": "Tab",
                    "items": [
                        {
                            "id": "g1",
                            "namespace": "default",
                            "type": "group_control",
                            "data": {
                                "autoHeight": True,
                                "buttonApply": False,
                                "buttonReset": False,
                                "updateControlsOnChange": True,
                                "impactType": "asGroup",
                                "impactTabsIds": None,
                                "group": [
                                    {
                                        "id": "c1",
                                        "title": "Filter",
                                        "namespace": "default",
                                        "sourceType": "dataset",
                                        "source": {
                                            "datasetId": "ds1ds1ds1ds1d",
                                            "datasetFieldId": "f1",
                                            "elementType": "select",
                                        },
                                        "defaults": {"f1": ""},
                                    }
                                ],
                            },
                        }
                    ],
                    "layout": [],
                    "aliases": {},
                }
            ],
        },
    }
    respx.get(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=us_group)
    )
    response = _rpc("getDashboard", {"dashboardId": DASH_ID})
    assert response.status_code == 200, response.text
    item = response.json()["entry"]["data"]["tabs"][0]["items"][0]
    assert item["type"] == "group_control"
    assert item["data"]["showGroupName"] is False
    assert item["data"].get("impactType") != "asGroup"
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(response.json())


@respx.mock
def test_get_dashboard_missing_entry_id_is_internal():
    us_no_id = {key: value for key, value in US_GET.items() if key != "entryId"}
    respx.get(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=us_no_id)
    )
    response = _rpc("getDashboard", {"dashboardId": DASH_ID})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"


@respx.mock
def test_get_dashboard_forwards_include_flags():
    route = respx.get(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=US_GET_PERMS)
    )
    response = _rpc(
        "getDashboard",
        {
            "dashboardId": DASH_ID,
            "includePermissions": True,
            "includeLinks": True,
            "includeFavorite": True,
            "revId": REV_ID,
            "branch": "saved",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["permissions"] == {
        "execute": True,
        "read": True,
        "edit": True,
        "admin": True,
    }
    params = dict(route.calls[0].request.url.params)
    assert params["includePermissionsInfo"] == "true"
    assert params["includeLinks"] == "true"
    assert params["includeFavorite"] == "true"
    assert params["revId"] == REV_ID
    assert params["branch"] == "saved"
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(body)


@respx.mock
def test_update_dashboard_posts_mode_and_data():
    updated = {**US_CREATE, "data": {**US_CREATE["data"], "salt": "updated"}}
    route = respx.post(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=updated)
    )
    response = _rpc(
        "updateDashboard",
        {
            "entry": {
                "entryId": DASH_ID,
                "data": {**MIN_DATA, "salt": "updated"},
                "meta": {"note": "save"},
            },
            "mode": "save",
            "lockToken": "tok-1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entry"]["entryId"] == DASH_ID
    assert body["entry"]["type"] == ""
    sent = json.loads(route.calls[0].request.content)
    assert sent["mode"] == "save"
    assert sent["data"]["salt"] == "updated"
    assert sent["meta"] == {"note": "save"}
    assert sent.get("lockToken") == "tok-1"
    from app.models.generated import GetDashboardV1Result

    GetDashboardV1Result.model_validate(body)


@respx.mock
def test_delete_dashboard_returns_empty_object():
    route = respx.delete(f"{US_HOST}/private/entries/{DASH_ID}").mock(
        return_value=httpx.Response(200, json=US_DELETE)
    )
    response = _rpc("deleteDashboard", {"dashboardId": DASH_ID, "lockToken": "tok-1"})
    assert response.status_code == 200, response.text
    assert response.json() == {}
    assert route.called


def test_json_lists_dashboard_methods():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    for name in (
        "createDashboard",
        "getDashboard",
        "updateDashboard",
        "deleteDashboard",
    ):
        assert f"/rpc/{name}" in paths
    assert "/rpc/createEditorChart" not in paths
