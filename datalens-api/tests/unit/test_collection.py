import json
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

AUTH_HOST = "http://auth.example:8080"
US_HOST = "http://us.example:8080"
US_PRIVATE_COLLECTIONS = f"{US_HOST}/private/v1/collections"
COL_ID = "col123col123a"

US_ITEM = {
    "collectionId": COL_ID,
    "title": "Demo",
    "description": None,
    "parentId": None,
    "tenantId": "common",
    "meta": {},
    "createdBy": "admin",
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedBy": "admin",
    "updatedAt": "2026-01-01T00:00:00.000Z",
}
US_CREATED = {**US_ITEM, "title": "T"}

US_STRUCTURE = {
    "items": [
        {
            "workbookId": "z4wtz6tg5194o",
            "collectionId": None,
            "title": "OpenSource Demo",
            "description": "",
            "tenantId": "common",
            "meta": {},
            "createdBy": "systemId",
            "createdAt": "2023-09-11T08:47:20.751Z",
            "updatedBy": "systemId",
            "updatedAt": "2023-09-11T08:47:20.751Z",
            "status": "active",
            "entity": "workbook",
        }
    ],
    "nextPageToken": None,
}

COLLECTION_PERMISSION_KEYS = (
    "listAccessBindings",
    "updateAccessBindings",
    "createSharedEntry",
    "createCollection",
    "createWorkbook",
    "limitedView",
    "view",
    "update",
    "copy",
    "move",
    "delete",
)


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
def test_create_collection_returns_id():
    route = respx.post(US_PRIVATE_COLLECTIONS).mock(
        return_value=httpx.Response(200, json=US_CREATED)
    )
    response = _rpc("createCollection", {"title": "T", "parentId": None})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["collectionId"] == COL_ID
    assert body["title"] == "T"
    assert route.called
    from app.models.generated import CreateCollectionResult

    CreateCollectionResult.model_validate(body)


@respx.mock
def test_get_collection_always_includes_permissions():
    respx.get(f"{US_PRIVATE_COLLECTIONS}/{COL_ID}").mock(
        return_value=httpx.Response(200, json=US_ITEM)
    )
    response = _rpc("getCollection", {"collectionId": COL_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["collectionId"] == COL_ID
    assert "permissions" in body
    perms = body["permissions"]
    for key in COLLECTION_PERMISSION_KEYS:
        assert key in perms
        assert perms[key] is True
    from app.models.generated import GetCollectionResult

    GetCollectionResult.model_validate(body)


@respx.mock
def test_get_collection_content_maps_structure_items():
    _mock_signin()
    route = respx.get(f"{US_HOST}/v1/structure-items").mock(
        return_value=httpx.Response(200, json=US_STRUCTURE)
    )
    response = _rpc(
        "getCollectionContent",
        {"collectionId": None, "page": "0", "pageSize": 10},
    )
    assert response.status_code == 200, response.text
    from app.models.generated import GetStructureItemsResult

    result = GetStructureItemsResult.model_validate(response.json())
    assert result.items[0].entity.value == "workbook"
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_update_collection_sends_jwt():
    _mock_signin()
    updated = {**US_ITEM, "title": "New"}
    route = respx.post(f"{US_HOST}/v1/collections/{COL_ID}/update").mock(
        return_value=httpx.Response(200, json=updated)
    )
    response = _rpc("updateCollection", {"collectionId": COL_ID, "title": "New"})
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "New"
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_delete_collection_wraps_collections():
    _mock_signin()
    respx.delete(f"{US_HOST}/v1/collections/{COL_ID}").mock(
        return_value=httpx.Response(200, json=US_ITEM)
    )
    response = _rpc("deleteCollection", {"collectionId": COL_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["collections"][0]["collectionId"] == COL_ID
    from app.models.generated import DeleteCollectionResult

    DeleteCollectionResult.model_validate(body)


@respx.mock
def test_delete_collection_empty_us_body_returns_200():
    _mock_signin()
    respx.delete(f"{US_HOST}/v1/collections/{COL_ID}").mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("deleteCollection", {"collectionId": COL_ID})
    assert response.status_code == 200, response.text
    assert response.json()["collections"][0]["collectionId"] == COL_ID


@respx.mock
def test_delete_collections_sends_jwt_and_ids():
    _mock_signin()
    route = respx.delete(f"{US_HOST}/v1/delete-collections").mock(
        return_value=httpx.Response(200, json={"collections": [US_ITEM]})
    )
    response = _rpc("deleteCollections", {"collectionIds": [COL_ID]})
    assert response.status_code == 200, response.text
    assert response.json()["collections"][0]["collectionId"] == COL_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_move_collection_sends_jwt():
    _mock_signin()
    moved = {**US_ITEM, "parentId": None}
    route = respx.post(f"{US_HOST}/v1/collections/{COL_ID}/move").mock(
        return_value=httpx.Response(200, json=moved)
    )
    response = _rpc("moveCollection", {"collectionId": COL_ID, "parentId": None})
    assert response.status_code == 200, response.text
    assert response.json()["collectionId"] == COL_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_move_collections_sends_jwt():
    _mock_signin()
    route = respx.post(f"{US_HOST}/v1/move-collections").mock(
        return_value=httpx.Response(200, json={"collections": [US_ITEM]})
    )
    response = _rpc(
        "moveCollections", {"collectionIds": [COL_ID], "parentId": None}
    )
    assert response.status_code == 200, response.text
    assert response.json()["collections"][0]["collectionId"] == COL_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_get_collections_by_ids_returns_array():
    _mock_signin()
    route = respx.post(f"{US_HOST}/v1/collections-get-list-by-ids").mock(
        return_value=httpx.Response(200, json=[US_ITEM])
    )
    response = _rpc("getCollectionsByIds", {"collectionIds": [COL_ID]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["collectionId"] == COL_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_get_collection_breadcrumbs_returns_array():
    _mock_signin()
    route = respx.get(f"{US_HOST}/v1/collections/{COL_ID}/breadcrumbs").mock(
        return_value=httpx.Response(200, json=[US_ITEM])
    )
    response = _rpc("getCollectionBreadcrumbs", {"collectionId": COL_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["collectionId"] == COL_ID
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_get_root_collection_permissions():
    _mock_signin()
    route = respx.get(f"{US_HOST}/v1/root-collection-permissions").mock(
        return_value=httpx.Response(
            200,
            json={"createCollectionInRoot": True, "createWorkbookInRoot": True},
        )
    )
    response = _rpc("getRootCollectionPermissions", {})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["createCollectionInRoot"] is True
    assert body["createWorkbookInRoot"] is True
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"
    from app.models.generated import GetRootCollectionPermissionsResult

    GetRootCollectionPermissionsResult.model_validate(body)
