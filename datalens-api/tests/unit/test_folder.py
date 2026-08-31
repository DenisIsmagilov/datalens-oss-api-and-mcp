import json
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

AUTH_HOST = "http://auth.example:8080"
US_HOST = "http://us.example:8080"
FOLDER_ID = "fld123fld123a"

US_FOLDER = {
    "entryId": FOLDER_ID,
    "scope": "folder",
    "type": "",
    "key": "Users/admin/demo-folder/",
    "unversionedData": {},
    "createdBy": "admin",
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedBy": "admin",
    "updatedAt": "2026-01-01T00:00:00.000Z",
    "savedId": "rev123rev123a",
    "revId": "rev123rev123a",
    "publishedId": None,
    "tenantId": "common",
    "data": {},
    "meta": {},
    "annotation": None,
    "hidden": False,
    "mirrored": False,
    "public": False,
    "workbookId": None,
    "collectionId": None,
    "version": None,
    "sourceVersion": None,
    "links": None,
}


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
def test_create_folder_returns_entry_id():
    route = respx.post(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(200, json=US_FOLDER)
    )
    response = _rpc("createFolder", {"key": "Users/admin/demo-folder/"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entryId"] == FOLDER_ID
    assert body["scope"] == "folder"
    assert body["type"] == ""
    assert body["key"] == "Users/admin/demo-folder/"
    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["scope"] == "folder"
    assert sent["key"] == "Users/admin/demo-folder/"
    from app.models.generated import CreateFolderResult

    CreateFolderResult.model_validate(body)


@respx.mock
def test_delete_folder_returns_empty_object():
    route = respx.delete(f"{US_HOST}/private/entries/{FOLDER_ID}").mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("deleteFolder", {"folderId": FOLDER_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {}
    assert route.called


@respx.mock
def test_move_folder_entry_sends_destination():
    moved = {
        "entryId": FOLDER_ID,
        "key": "Users/admin/other/demo-folder/",
        "scope": "folder",
        "type": "",
    }
    route = respx.post(f"{US_HOST}/private/entries/{FOLDER_ID}").mock(
        return_value=httpx.Response(200, json=[moved])
    )
    response = _rpc(
        "moveFolderEntry",
        {"entryId": FOLDER_ID, "destination": "Users/admin/other/"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["entryId"] == FOLDER_ID
    assert body[0]["key"] == "Users/admin/other/demo-folder/"
    sent = json.loads(route.calls[0].request.content)
    assert sent["destination"] == "Users/admin/other/"
    from app.models.generated import MoveEntryResult

    MoveEntryResult.model_validate(body)


@respx.mock
def test_get_permissions_uses_jwt_access_description():
    _mock_signin()
    route = respx.get(f"{US_HOST}/v1/entries/{FOLDER_ID}/access-description").mock(
        return_value=httpx.Response(200, json={"accessDescription": None})
    )
    response = _rpc("getPermissions", {"entryId": FOLDER_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "editable" in body
    assert "pendingPermissions" in body
    assert "permissions" in body
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"
    from app.models.generated import GetPermissionsResult

    GetPermissionsResult.model_validate(body)


def test_json_lists_mvp_methods_and_excludes_out_of_scope():
    client = TestClient(create_app())
    spec = client.get("/json/").json()
    paths = spec["paths"]
    for name in ("getWorkbooksList", "createCollection", "getEntries", "createFolder"):
        assert f"/rpc/{name}" in paths
    for name in ("createEditorChart", "createReport", "assignLicenses"):
        assert f"/rpc/{name}" not in paths
    assert "/rpc/dlsSuggest" not in paths
    assert "/rpc/modifyPermissions" not in paths
