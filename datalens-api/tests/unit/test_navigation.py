import json

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

US_HOST = "http://us.example:8080"
ENTRY_ID = "wid123wid123a"

US_ENTRY = {
    "entryId": ENTRY_ID,
    "key": "OpenSource Demo/chart",
    "scope": "widget",
    "type": "graph",
    "meta": {},
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedAt": "2026-01-01T00:00:00.000Z",
    "createdBy": "admin",
    "updatedBy": "admin",
    "savedId": "sav123sav123a",
    "publishedId": None,
    "hidden": False,
    "workbookId": "wb123wb123wb1",
    "collectionId": None,
    "isFavorite": False,
    "isLocked": False,
    "links": None,
    "name": "chart",
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
def test_get_entries_maps_us_payload():
    route = respx.post(f"{US_HOST}/private/v1/get-entries").mock(
        return_value=httpx.Response(
            200, json={"entries": [US_ENTRY], "nextPageToken": None}
        )
    )
    response = _rpc("getEntries", {"ids": [ENTRY_ID], "pageSize": 10})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entries"][0]["entryId"] == ENTRY_ID
    assert body["entries"][0]["name"] == "chart"
    assert body["entries"][0]["key"] == "OpenSource Demo/chart"
    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["ids"] == [ENTRY_ID]
    from app.models.generated import GetEntriesV2Result

    GetEntriesV2Result.model_validate(body)


@respx.mock
def test_list_directory_maps_folder_page():
    route = respx.get(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(
            200, json={"entries": [US_ENTRY], "nextPageToken": None}
        )
    )
    response = _rpc("listDirectory", {"path": "Users/admin/", "page": 0, "pageSize": 10})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hasNextPage"] is False
    assert body["breadCrumbs"] == []
    assert body["entries"][0]["entryId"] == ENTRY_ID
    assert body["entries"][0]["name"] == "chart"
    assert route.called
    from app.models.generated import ListDirectoryResult

    ListDirectoryResult.model_validate(body)
