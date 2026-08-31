import json
from urllib.parse import quote

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.errors import ApiError
from app.main import create_app

AUTH_HOST = "http://auth.example:8080"
META_HOST = "http://meta-manager.example:8080"
IMPORT_ID = "zumftaxxz07ci"
WB_ID = "2xpiwduga8qal"
COLLECTION_ID = "col12encoded1"

START_URL = f"{META_HOST}/workbooks/import"
STATUS_URL = f"{META_HOST}/workbooks/import/{IMPORT_ID}"

IMPORT_DATA = {
    "export": {"version": "v1", "entries": {}},
    "hash": "recon-hash-not-invented",
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
def test_start_workbook_import_returns_ids():
    _mock_signin()
    route = respx.post(START_URL).mock(
        return_value=httpx.Response(
            200, json={"importId": IMPORT_ID, "workbookId": WB_ID}
        )
    )
    response = _rpc(
        "startWorkbookImport",
        {
            "title": "imported-wb",
            "description": "from export",
            "collectionId": COLLECTION_ID,
            "data": IMPORT_DATA,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"importId": IMPORT_ID, "workbookId": WB_ID}
    sent = json.loads(route.calls[0].request.content)
    assert sent == {
        "title": "imported-wb",
        "description": "from export",
        "collectionId": COLLECTION_ID,
        "data": IMPORT_DATA,
    }
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_start_workbook_import_omits_null_optional_fields():
    _mock_signin()
    route = respx.post(START_URL).mock(
        return_value=httpx.Response(
            200, json={"importId": IMPORT_ID, "workbookId": WB_ID}
        )
    )
    response = _rpc(
        "startWorkbookImport",
        {"title": "imported-wb", "collectionId": None, "data": IMPORT_DATA},
    )
    assert response.status_code == 200, response.text
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"title": "imported-wb", "data": IMPORT_DATA}
    assert "collectionId" not in sent
    assert "description" not in sent


@respx.mock
def test_start_workbook_import_missing_import_id_is_internal():
    _mock_signin()
    respx.post(START_URL).mock(return_value=httpx.Response(200, json={"workbookId": WB_ID}))
    response = _rpc(
        "startWorkbookImport",
        {"title": "imported-wb", "collectionId": None, "data": IMPORT_DATA},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"


@respx.mock
def test_start_workbook_import_missing_workbook_id_is_internal():
    _mock_signin()
    respx.post(START_URL).mock(
        return_value=httpx.Response(200, json={"importId": IMPORT_ID})
    )
    response = _rpc(
        "startWorkbookImport",
        {"title": "imported-wb", "collectionId": None, "data": IMPORT_DATA},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"


@respx.mock
def test_get_workbook_import_status_maps_fields():
    _mock_signin()
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "importId": IMPORT_ID,
                "workbookId": WB_ID,
                "status": "success",
                "progress": 0,
            },
        )
    )
    response = _rpc("getWorkbookImportStatus", {"importId": IMPORT_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["importId"] == IMPORT_ID
    assert body["workbookId"] == WB_ID
    assert body["status"] == "success"
    assert body["progress"] == 0
    assert body.get("notifications") in ([], None)


@respx.mock
def test_get_workbook_import_status_missing_progress_is_zero():
    _mock_signin()
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "importId": IMPORT_ID,
                "workbookId": WB_ID,
                "status": "pending",
            },
        )
    )
    response = _rpc("getWorkbookImportStatus", {"importId": IMPORT_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["progress"] == 0
    assert body.get("notifications") in ([], None)


def test_json_lists_six_transfer_methods_and_excludes_unregistered():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    for name in (
        "startWorkbookExport",
        "getWorkbookExportStatus",
        "getWorkbookExportResult",
        "cancelWorkbookExport",
        "startWorkbookImport",
        "getWorkbookImportStatus",
    ):
        assert f"/rpc/{name}" in paths
    assert "/rpc/cancelWorkbookImport" not in paths
    assert "/rpc/createEditorChart" not in paths


def test_import_ids_to_cloud_does_not_invent_ids():
    from app.adapters.transfer import import_ids_to_cloud

    adapted = import_ids_to_cloud(
        {"importId": IMPORT_ID, "workbookId": WB_ID}, what="start import"
    )
    assert adapted == {"importId": IMPORT_ID, "workbookId": WB_ID}


def test_import_ids_to_cloud_missing_import_id_is_internal():
    from app.adapters.transfer import import_ids_to_cloud

    with pytest.raises(ApiError) as exc_info:
        import_ids_to_cloud({"workbookId": WB_ID}, what="start import")
    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "INTERNAL"


def test_import_status_to_cloud_defaults_progress_and_notifications():
    from app.adapters.transfer import import_status_to_cloud

    adapted = import_status_to_cloud(
        {"importId": IMPORT_ID, "workbookId": WB_ID, "status": "pending"}
    )
    assert adapted["importId"] == IMPORT_ID
    assert adapted["workbookId"] == WB_ID
    assert adapted["status"] == "pending"
    assert adapted["progress"] == 0
    assert adapted["notifications"] == []
