import json
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

AUTH_HOST = "http://auth.example:8080"
CONTROL_HOST = "http://control-api.example:8080"
CONN_ID = "conn123conn12"
CONNECTIONS_URL = f"{CONTROL_HOST}/api/v1/connections/"
CONNECTION_URL = f"{CONTROL_HOST}/api/v1/connections/{CONN_ID}"

CREATE_BODY = {
    "type": "clickhouse",
    "name": "ch",
    "host": "127.0.0.1",
    "port": 8123,
    "dir_path": "/",
    "username": "u",
    "password": "x",
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
def test_create_connection_returns_id():
    _mock_signin()
    respx.post("http://control-api.example:8080/api/v1/connections/").mock(
        return_value=httpx.Response(200, json={"id": "conn123conn12"})
    )
    response = _rpc("createConnection", {
        "type": "clickhouse",
        "name": "ch",
        "host": "127.0.0.1",
        "port": 8123,
        "dir_path": "/",
        "username": "u",
        "password": "x",
    })
    assert response.status_code == 200, response.text
    assert response.json()["id"] == "conn123conn12"


@respx.mock
def test_get_connection_ok():
    _mock_signin()
    respx.get("http://control-api.example:8080/api/v1/connections/conn123conn12").mock(
        return_value=httpx.Response(200, json={
            "id": "conn123conn12",
            "type": "clickhouse",
            "name": "ch",
            "host": "127.0.0.1",
            "port": 8123,
            "dir_path": "/",
        })
    )
    response = _rpc("getConnection", {"connectionId": "conn123conn12"})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == "conn123conn12"
    assert "password" not in response.json() or response.json().get("password") in (None, "")


@respx.mock
def test_delete_connection_empty():
    _mock_signin()
    respx.delete("http://control-api.example:8080/api/v1/connections/conn123conn12").mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("deleteConnection", {"connectionId": "conn123conn12"})
    assert response.status_code == 200
    assert response.json() == {}


@respx.mock
def test_update_connection_empty():
    _mock_signin()
    route = respx.put(CONNECTION_URL).mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("updateConnection", {"connectionId": CONN_ID, "data": {"name": "n2"}})
    assert response.status_code == 200, response.text
    assert response.json() == {}
    assert json.loads(route.calls[0].request.content) == {"name": "n2"}


@respx.mock
def test_delete_connection_null_body_is_empty():
    _mock_signin()
    respx.delete(CONNECTION_URL).mock(
        return_value=httpx.Response(200, json=None)
    )
    response = _rpc("deleteConnection", {"connectionId": CONN_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {}


@respx.mock
def test_get_connection_maps_db_type_and_strips_password():
    _mock_signin()
    respx.get(CONNECTION_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": CONN_ID,
                "db_type": "clickhouse",
                "name": "ch",
                "host": "127.0.0.1",
                "port": 8123,
                "password": "secret",
            },
        )
    )
    response = _rpc("getConnection", {"connectionId": CONN_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == CONN_ID
    assert body.get("type") == "clickhouse"
    assert "password" not in body


@respx.mock
def test_get_connection_sends_rev_id_and_dataset_header():
    _mock_signin()
    route = respx.get(CONNECTION_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": CONN_ID,
                "type": "clickhouse",
                "name": "ch",
                "host": "127.0.0.1",
                "port": 8123,
            },
        )
    )
    response = _rpc(
        "getConnection",
        {
            "connectionId": CONN_ID,
            "rev_id": "rev1",
            "bindedDatasetId": "ds1",
        },
    )
    assert response.status_code == 200, response.text
    request = route.calls[0].request
    assert request.url.params["rev_id"] == "rev1"
    assert request.headers["x-dl-dataset-id"] == "ds1"


@respx.mock
def test_create_connection_drops_operation_and_passes_body():
    _mock_signin()
    route = respx.post(CONNECTIONS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"id": CONN_ID, "operation": {"id": "op1", "done": True}},
        )
    )
    response = _rpc("createConnection", CREATE_BODY)
    assert response.status_code == 200, response.text
    assert response.json() == {"id": CONN_ID}
    sent = json.loads(route.calls[0].request.content)
    assert sent["type"] == "clickhouse"
    assert sent["password"] == "x"
    assert sent.get("secure") is not True


def test_json_lists_create_connection_and_excludes_editor_chart():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    assert "/rpc/createConnection" in paths
    assert "/rpc/createEditorChart" not in paths


def test_connection_to_cloud_maps_db_type_and_strips_password():
    from app.adapters.connection import connection_to_cloud

    adapted = connection_to_cloud(
        {
            "id": CONN_ID,
            "db_type": "clickhouse",
            "name": "ch",
            "host": "127.0.0.1",
            "port": 8123,
            "password": "secret",
            "options": {"allow_dataset_usage": True},
            "workbook_id": "wb123wb123wb",
            "dir_path": "/",
        }
    )
    assert adapted["type"] == "clickhouse"
    assert "password" not in adapted
    assert "db_type" not in adapted
    assert "options" not in adapted
    assert "workbook_id" not in adapted
    assert "dir_path" not in adapted


def test_connection_to_cloud_fills_empty_password_for_mssql():
    from app.adapters.connection import connection_to_cloud
    from app.models.generated import ConnectionRead

    adapted = connection_to_cloud(
        {
            "id": CONN_ID,
            "db_type": "mssql",
            "name": "BI_Exchange",
            "host": "db.example",
            "port": 1433,
            "username": "reader",
            "db_name": "bi",
            "raw_sql_level": "dashsql",
            "data_export_forbidden": "off",
            "workbook_id": "wb123wb123wb",
        }
    )
    assert adapted["type"] == "mssql"
    assert adapted["password"] == ""
    ConnectionRead.model_validate(adapted)


def test_create_connection_to_cloud_missing_id_is_internal():
    import pytest

    from app.adapters.connection import create_connection_to_cloud
    from app.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        create_connection_to_cloud({"operation": {"id": "op1"}})
    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "INTERNAL"
    assert "id" in exc_info.value.message.lower()

    with pytest.raises(ApiError) as exc_info:
        create_connection_to_cloud(None)
    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "INTERNAL"


def test_empty_to_cloud_coerces_none():
    from app.adapters.connection import empty_to_cloud

    assert empty_to_cloud(None) == {}
    assert empty_to_cloud({}) == {}
