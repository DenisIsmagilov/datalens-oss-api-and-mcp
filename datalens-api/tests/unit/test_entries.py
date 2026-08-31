import json
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

AUTH_HOST = "http://auth.example:8080"
US_HOST = "http://us.example:8080"
ENTRY_ID = "ent123ent123a"

US_RENAMED = {
    "entryId": ENTRY_ID,
    "key": "Users/admin/renamed-folder/",
    "scope": "folder",
    "type": "",
    "updatedAt": "2026-01-02T00:00:00.000Z",
    "updatedBy": "admin",
}

US_RELATION = {
    "entryId": ENTRY_ID,
    "key": None,
    "scope": "dataset",
    "type": "graph",
    "createdAt": "2026-01-01T00:00:00.000Z",
    "public": False,
    "tenantId": "common",
    "workbookId": "wb123wb123wb1",
    "collectionId": None,
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
def test_rename_entry_returns_array():
    route = respx.post(f"{US_HOST}/private/entries/{ENTRY_ID}/rename").mock(
        return_value=httpx.Response(200, json=[US_RENAMED])
    )
    response = _rpc("renameEntry", {"entryId": ENTRY_ID, "name": "renamed-folder"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["entryId"] == ENTRY_ID
    assert body[0]["key"] == "Users/admin/renamed-folder/"
    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["name"] == "renamed-folder"
    from app.models.generated import RenameEntryResult

    RenameEntryResult.model_validate(body)


@respx.mock
def test_get_entries_relations_maps_relations():
    route = respx.post(f"{US_HOST}/private/v1/get-entries-relations").mock(
        return_value=httpx.Response(
            200, json={"relations": [US_RELATION], "nextPageToken": None}
        )
    )
    response = _rpc(
        "getEntriesRelations",
        {"entryIds": [ENTRY_ID], "linkDirection": "from"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["relations"][0]["entryId"] == ENTRY_ID
    assert body["relations"][0]["public"] is False
    assert route.called
    from app.models.generated import GetEntriesRelationsResult

    GetEntriesRelationsResult.model_validate(body)


@respx.mock
def test_get_entries_permissions_uses_jwt_access_description():
    _mock_signin()
    route = respx.get(f"{US_HOST}/v1/entries/{ENTRY_ID}/access-description").mock(
        return_value=httpx.Response(
            200,
            json={"permissions": {"execute": True, "read": True, "edit": False, "admin": False}},
        )
    )
    response = _rpc("getEntriesPermissions", {"entryIds": [ENTRY_ID]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body[ENTRY_ID]["permissions"]["read"] is True
    assert body[ENTRY_ID]["permissions"]["edit"] is False
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"
    from app.models.generated import GetEntriesPermissionsResult

    GetEntriesPermissionsResult.model_validate(body)
