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
WB_ID = "xskdruz08fa0g"
EXPORT_ID = "ytles0xc20smh"
EXPORT_HASH = "recon-hash-not-invented"

START_URL = f"{META_HOST}/workbooks/export"
STATUS_URL = f"{META_HOST}/workbooks/export/{EXPORT_ID}"
RESULT_URL = f"{META_HOST}/workbooks/export/{EXPORT_ID}/result"
CANCEL_URL = f"{META_HOST}/workbooks/export/{EXPORT_ID}/cancel"

EXPORT_DATA = {"version": "v1", "entries": {}}


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
def test_start_workbook_export_returns_export_id():
    _mock_signin()
    route = respx.post(START_URL).mock(
        return_value=httpx.Response(200, json={"exportId": EXPORT_ID})
    )
    response = _rpc("startWorkbookExport", {"workbookId": WB_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {"exportId": EXPORT_ID}
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"workbookId": WB_ID}
    assert route.calls[0].request.headers["authorization"] == "Bearer test-user-jwt"


@respx.mock
def test_start_workbook_export_missing_export_id_is_internal():
    _mock_signin()
    respx.post(START_URL).mock(return_value=httpx.Response(200, json={}))
    response = _rpc("startWorkbookExport", {"workbookId": WB_ID})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"


@respx.mock
def test_get_workbook_export_status_maps_fields():
    _mock_signin()
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "exportId": EXPORT_ID,
                "status": "success",
                "progress": 0,
                "notifications": [],
            },
        )
    )
    response = _rpc("getWorkbookExportStatus", {"exportId": EXPORT_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exportId"] == EXPORT_ID
    assert body["status"] == "success"
    assert body["progress"] == 0
    assert body.get("notifications") in ([], None)


@respx.mock
def test_get_workbook_export_status_missing_progress_is_zero():
    _mock_signin()
    respx.get(STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"exportId": EXPORT_ID, "status": "pending"},
        )
    )
    response = _rpc("getWorkbookExportStatus", {"exportId": EXPORT_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["progress"] == 0
    assert body.get("notifications") in ([], None)


@respx.mock
def test_get_workbook_export_result_returns_export_and_hash():
    _mock_signin()
    respx.get(RESULT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "exportId": EXPORT_ID,
                "status": "success",
                "data": {"export": EXPORT_DATA, "hash": EXPORT_HASH},
            },
        )
    )
    response = _rpc("getWorkbookExportResult", {"exportId": EXPORT_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exportId"] == EXPORT_ID
    assert body["status"] == "success"
    assert body["data"]["export"] == EXPORT_DATA
    assert body["data"]["hash"] == EXPORT_HASH


@respx.mock
def test_get_workbook_export_result_not_completed_is_invalid_argument():
    _mock_signin()
    respx.get(RESULT_URL).mock(
        return_value=httpx.Response(
            409,
            json={
                "code": "META_MANAGER.WORKBOOK_EXPORT_NOT_COMPLETED",
                "message": "The export is not completed. It is either still in progress or has failed",
            },
        )
    )
    response = _rpc("getWorkbookExportResult", {"exportId": EXPORT_ID})
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_ARGUMENT"
    assert "WORKBOOK_EXPORT_NOT_COMPLETED" in json.dumps(response.json())


@respx.mock
def test_get_workbook_export_result_missing_hash_is_internal():
    _mock_signin()
    respx.get(RESULT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "exportId": EXPORT_ID,
                "status": "success",
                "data": {"export": EXPORT_DATA},
            },
        )
    )
    response = _rpc("getWorkbookExportResult", {"exportId": EXPORT_ID})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert "hash" in response.json()["message"].lower()


@respx.mock
def test_get_workbook_export_result_missing_export_is_internal():
    _mock_signin()
    respx.get(RESULT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "exportId": EXPORT_ID,
                "status": "success",
                "data": {"hash": EXPORT_HASH},
            },
        )
    )
    response = _rpc("getWorkbookExportResult", {"exportId": EXPORT_ID})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert "export" in response.json()["message"].lower()


@respx.mock
def test_cancel_workbook_export_returns_export_id():
    _mock_signin()
    route = respx.post(CANCEL_URL).mock(
        return_value=httpx.Response(200, json={"exportId": EXPORT_ID})
    )
    response = _rpc("cancelWorkbookExport", {"exportId": EXPORT_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {"exportId": EXPORT_ID}
    assert route.calls[0].request.content in (b"", b"null")


def test_json_lists_export_methods():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    assert "/rpc/startWorkbookExport" in paths
    assert "/rpc/getWorkbookExportStatus" in paths
    assert "/rpc/getWorkbookExportResult" in paths
    assert "/rpc/cancelWorkbookExport" in paths


def test_export_status_to_cloud_defaults_progress_and_notifications():
    from app.adapters.transfer import export_status_to_cloud

    adapted = export_status_to_cloud({"exportId": EXPORT_ID, "status": "pending"})
    assert adapted["exportId"] == EXPORT_ID
    assert adapted["status"] == "pending"
    assert adapted["progress"] == 0
    assert adapted.get("notifications") in ([], None)


def test_export_result_to_cloud_missing_hash_is_internal():
    from app.adapters.transfer import export_result_to_cloud

    with pytest.raises(ApiError) as exc_info:
        export_result_to_cloud(
            {
                "exportId": EXPORT_ID,
                "status": "success",
                "data": {"export": EXPORT_DATA},
            }
        )
    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "INTERNAL"


def test_export_result_to_cloud_does_not_invent_hash():
    from app.adapters.transfer import export_result_to_cloud

    adapted = export_result_to_cloud(
        {
            "exportId": EXPORT_ID,
            "status": "success",
            "data": {"export": EXPORT_DATA, "hash": EXPORT_HASH},
        }
    )
    assert adapted["data"]["hash"] == EXPORT_HASH
    assert adapted["data"]["export"] == EXPORT_DATA
