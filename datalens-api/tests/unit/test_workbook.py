import json
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

US_LIST = {
    "workbooks": [
        {
            "workbookId": "abc123abc123a",
            "collectionId": None,
            "title": "Demo",
            "description": None,
            "tenantId": "common",
            "meta": {},
            "createdBy": "admin",
            "createdAt": "2026-01-01T00:00:00.000Z",
            "updatedBy": "admin",
            "updatedAt": "2026-01-01T00:00:00.000Z",
            "status": "active",
        }
    ],
    "nextPageToken": None,
}

AUTH_HOST = "http://auth.example:8080"
US_HOST = "http://us.example:8080"
US_LIST_URL = f"{US_HOST}/v2/workbooks"
US_PRIVATE_WORKBOOKS = f"{US_HOST}/private/v2/workbooks"
WB_ID = "abc123abc123a"
US_ITEM = US_LIST["workbooks"][0]
US_CREATED = {**US_ITEM, "title": "T"}


def _mock_signin(token: str = "test-user-jwt") -> None:
    cookie = quote(json.dumps({"accessToken": token, "refreshToken": "r"}))
    respx.post(f"{AUTH_HOST}/signin").mock(
        return_value=httpx.Response(
            200,
            json={"accessToken": token},
            headers={"Set-Cookie": f"auth={cookie}; Path=/; HttpOnly"},
        )
    )


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
def test_get_workbooks_list_maps_us_payload():
    _mock_signin()
    respx.get(US_LIST_URL).mock(return_value=httpx.Response(200, json=US_LIST))
    response = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workbooks"][0]["workbookId"] == "abc123abc123a"
    assert body["workbooks"][0]["title"] == "Demo"


@respx.mock
def test_get_workbooks_list_reads_jwt_from_auth_cookie():
    cookie = quote(json.dumps({"accessToken": "cookie-jwt", "refreshToken": "r"}))
    respx.post(f"{AUTH_HOST}/signin").mock(
        return_value=httpx.Response(
            200,
            json={"message": "Success"},
            headers={"Set-Cookie": f"auth={cookie}; Path=/; HttpOnly"},
        )
    )
    route = respx.get(US_LIST_URL).mock(
        return_value=httpx.Response(200, json={"workbooks": []})
    )
    response = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    assert route.calls[0].request.headers["authorization"] == "Bearer cookie-jwt"


@respx.mock
def test_get_workbooks_list_sends_user_jwt():
    _mock_signin("live-jwt-token")
    route = respx.get(US_LIST_URL).mock(
        return_value=httpx.Response(200, json={"workbooks": []})
    )
    response = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    assert route.called
    assert route.calls[0].request.headers["authorization"] == "Bearer live-jwt-token"


@respx.mock
def test_get_workbooks_list_passes_page_zero():
    _mock_signin()
    route = respx.get(US_LIST_URL).mock(
        return_value=httpx.Response(200, json={"workbooks": []})
    )
    response = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    assert route.calls[0].request.url.params["page"] == "0"


@respx.mock
def test_get_workbooks_list_coerces_page_size_to_int():
    _mock_signin()
    route = respx.get(US_LIST_URL).mock(
        return_value=httpx.Response(200, json={"workbooks": []})
    )
    response = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10.0})
    assert response.status_code == 200, response.text
    assert route.calls[0].request.url.params["pageSize"] == "10"


@respx.mock
def test_get_workbooks_list_omits_permissions_by_default():
    _mock_signin()
    respx.get(US_LIST_URL).mock(return_value=httpx.Response(200, json=US_LIST))
    body = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10}).json()
    assert "permissions" not in body["workbooks"][0]


@respx.mock
def test_get_workbooks_list_includes_permissions_when_requested():
    _mock_signin()
    respx.get(US_LIST_URL).mock(return_value=httpx.Response(200, json=US_LIST))
    body = _rpc(
        "getWorkbooksList",
        {"page": 0, "pageSize": 10, "includePermissionsInfo": True},
    ).json()
    perms = body["workbooks"][0]["permissions"]
    assert perms["view"] is True
    assert perms["copy"] is True


@respx.mock
def test_get_workbooks_list_absent_next_page_token():
    _mock_signin()
    respx.get(US_LIST_URL).mock(
        return_value=httpx.Response(200, json={"workbooks": []})
    )
    response = _rpc("getWorkbooksList", {"page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    assert response.json().get("nextPageToken") is None


def test_workbook_to_cloud_omits_permissions_by_default():
    from app.adapters.workbook import workbook_to_cloud

    item = workbook_to_cloud(US_LIST["workbooks"][0], include_permissions=False)
    assert "permissions" not in item
    assert item["workbookId"] == "abc123abc123a"


def test_workbook_to_cloud_uses_us_permissions_when_present():
    from app.adapters.common import WORKBOOK_PERMISSIONS_ALL
    from app.adapters.workbook import workbook_to_cloud

    raw = {**US_LIST["workbooks"][0], "permissions": {"view": False, "copy": True}}
    item = workbook_to_cloud(raw, include_permissions=False)
    assert item["permissions"]["view"] is False
    assert item["permissions"]["copy"] is True
    assert set(item["permissions"]) == set(WORKBOOK_PERMISSIONS_ALL)
    assert item["permissions"]["delete"] is True


def test_workbook_to_cloud_merges_partial_permissions():
    from app.adapters.common import WORKBOOK_PERMISSIONS_ALL
    from app.adapters.workbook import fill_workbook_permissions, workbook_to_cloud

    partial = {"view": False}
    filled = fill_workbook_permissions(partial)
    assert filled["view"] is False
    assert filled["update"] is True
    assert set(filled) == set(WORKBOOK_PERMISSIONS_ALL)

    raw = {**US_LIST["workbooks"][0], "permissions": partial}
    item = workbook_to_cloud(raw, include_permissions=True)
    assert item["permissions"] == filled



@respx.mock
def test_create_workbook_returns_id_and_operation_done():
    route = respx.post(US_PRIVATE_WORKBOOKS).mock(
        return_value=httpx.Response(200, json=US_CREATED)
    )
    response = _rpc("createWorkbook", {"title": "T"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workbookId"] == WB_ID
    assert body["operation"]["done"] is True
    assert route.called
    from app.adapters.common import normalize_operation

    synthesized = normalize_operation(None, workbook=US_CREATED)
    assert synthesized["done"] is True
    assert synthesized["id"] == WB_ID
    assert body["operation"]["id"] == synthesized["id"]
    assert int(body["operation"]["createdAt"]["seconds"]) >= 1_000_000_000


def test_normalize_operation_does_not_copy_garbage_seconds():
    from app.adapters.common import normalize_operation

    garbage = {
        "id": WB_ID,
        "description": "Datalens operation",
        "createdBy": "",
        "createdAt": {"nanos": 654223256, "seconds": "245949"},
        "modifiedAt": {"nanos": 654223256, "seconds": "245949"},
        "metadata": {},
        "done": True,
    }
    op = normalize_operation(garbage, workbook=US_CREATED)
    assert op["done"] is True
    assert op["createdAt"]["seconds"] != "245949"
    assert int(op["createdAt"]["seconds"]) >= 1_000_000_000


@respx.mock
def test_get_workbook_always_includes_permissions():
    respx.get(f"{US_PRIVATE_WORKBOOKS}/{WB_ID}").mock(
        return_value=httpx.Response(200, json=US_ITEM)
    )
    response = _rpc("getWorkbook", {"workbookId": WB_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "permissions" in body
    assert body["permissions"]["view"] is True
    assert body["workbookId"] == WB_ID


@respx.mock
def test_delete_workbook_returns_200():
    respx.delete(f"{US_PRIVATE_WORKBOOKS}/{WB_ID}").mock(
        return_value=httpx.Response(200, json=US_ITEM)
    )
    response = _rpc("deleteWorkbook", {"workbookId": WB_ID})
    assert response.status_code == 200, response.text
    from app.models.generated import Workbook

    Workbook.model_validate(response.json())


@respx.mock
def test_delete_workbook_empty_us_body_returns_200():
    respx.delete(f"{US_PRIVATE_WORKBOOKS}/{WB_ID}").mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("deleteWorkbook", {"workbookId": WB_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workbookId"] == WB_ID
    from app.models.generated import Workbook

    Workbook.model_validate(body)


@respx.mock
def test_delete_workbooks_empty_us_body_returns_200():
    _mock_signin()
    respx.delete(f"{US_HOST}/v2/delete-workbooks").mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("deleteWorkbooks", {"workbookIds": [WB_ID]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workbooks"][0]["workbookId"] == WB_ID
    from app.models.generated import Workbook

    Workbook.model_validate(body["workbooks"][0])


@respx.mock
def test_update_workbook_maps_title():
    updated = {**US_ITEM, "title": "New"}
    route = respx.post(f"{US_PRIVATE_WORKBOOKS}/{WB_ID}/update").mock(
        return_value=httpx.Response(200, json=updated)
    )
    response = _rpc("updateWorkbook", {"workbookId": WB_ID, "title": "New"})
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "New"
    assert route.called


@respx.mock
def test_delete_workbooks_sends_jwt_and_ids():
    _mock_signin()
    route = respx.delete(f"{US_HOST}/v2/delete-workbooks").mock(
        return_value=httpx.Response(200, json={"workbooks": [US_ITEM]})
    )
    response = _rpc("deleteWorkbooks", {"workbookIds": [WB_ID]})
    assert response.status_code == 200, response.text
    assert response.json()["workbooks"][0]["workbookId"] == WB_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_move_workbook_sends_jwt():
    _mock_signin()
    moved = {**US_ITEM, "collectionId": None}
    route = respx.post(f"{US_HOST}/v2/workbooks/{WB_ID}/move").mock(
        return_value=httpx.Response(200, json=moved)
    )
    response = _rpc("moveWorkbook", {"workbookId": WB_ID, "collectionId": None})
    assert response.status_code == 200, response.text
    assert response.json()["workbookId"] == WB_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_move_workbooks_sends_jwt():
    _mock_signin()
    route = respx.post(f"{US_HOST}/v2/move-workbooks").mock(
        return_value=httpx.Response(200, json={"workbooks": [US_ITEM]})
    )
    response = _rpc(
        "moveWorkbooks", {"workbookIds": [WB_ID], "collectionId": None}
    )
    assert response.status_code == 200, response.text
    assert response.json()["workbooks"][0]["workbookId"] == WB_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_get_workbooks_by_ids_returns_array():
    _mock_signin()
    route = respx.post(f"{US_HOST}/v2/workbooks-get-list-by-ids").mock(
        return_value=httpx.Response(200, json=[US_ITEM])
    )
    response = _rpc("getWorkbooksByIds", {"workbookIds": [WB_ID]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["workbookId"] == WB_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_get_workbook_entries_maps_empty_list():
    route = respx.get(f"{US_PRIVATE_WORKBOOKS}/{WB_ID}/entries").mock(
        return_value=httpx.Response(200, json={"entries": []})
    )
    response = _rpc("getWorkbookEntries", {"workbookId": WB_ID, "page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    assert response.json()["entries"] == []
    assert route.called
