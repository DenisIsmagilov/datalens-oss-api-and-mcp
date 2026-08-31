import json
from urllib.parse import quote

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app

AUTH_HOST = "http://auth.example:8080"
CONTROL_HOST = "http://control-api.example:8080"
DS_ID = "ds123ds123ds1"
DATASETS_URL = f"{CONTROL_HOST}/api/v1/datasets/"
DATASET_DRAFT_URL = f"{CONTROL_HOST}/api/v1/datasets/{DS_ID}/versions/draft"
DATASET_VALIDATE_URL = f"{DATASET_DRAFT_URL}/validators/schema"
DATASET_URL = f"{CONTROL_HOST}/api/v1/datasets/{DS_ID}"

CREATE_BODY = {
    "dataset": {},
    "name": "ds1",
    "workbook_id": "wb123wb123wb",
}

DATASET_READ = {
    "id": DS_ID,
    "dataset": {},
    "name": "ds1",
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
def test_create_dataset_returns_id():
    _mock_signin()
    respx.post(DATASETS_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc("createDataset", CREATE_BODY)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == DS_ID
    assert response.json()["name"] == "ds1"


@respx.mock
def test_get_dataset_ok():
    _mock_signin()
    respx.get(DATASET_DRAFT_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc("getDataset", {"datasetId": DS_ID})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == DS_ID
    assert response.json()["name"] == "ds1"


@respx.mock
def test_delete_dataset_empty():
    _mock_signin()
    respx.delete(DATASET_URL).mock(
        return_value=httpx.Response(200, json={})
    )
    response = _rpc("deleteDataset", {"datasetId": DS_ID})
    assert response.status_code == 200
    assert response.json() == {}


@respx.mock
def test_update_dataset_returns_dataset():
    _mock_signin()
    route = respx.put(DATASET_DRAFT_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc(
        "updateDataset",
        {"datasetId": DS_ID, "data": {"dataset": {}, "name": "ds2"}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == DS_ID
    assert json.loads(route.calls[0].request.content) == {"dataset": {}, "name": "ds2"}


@respx.mock
def test_delete_dataset_null_body_is_empty():
    _mock_signin()
    respx.delete(DATASET_URL).mock(
        return_value=httpx.Response(200, json=None)
    )
    response = _rpc("deleteDataset", {"datasetId": DS_ID})
    assert response.status_code == 200, response.text
    assert response.json() == {}


@respx.mock
def test_get_dataset_sends_rev_id():
    _mock_signin()
    route = respx.get(DATASET_DRAFT_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc("getDataset", {"datasetId": DS_ID, "rev_id": "rev1"})
    assert response.status_code == 200, response.text
    assert route.calls[0].request.url.params["rev_id"] == "rev1"


@respx.mock
def test_create_dataset_passes_body_and_drops_errors():
    _mock_signin()
    route = respx.post(DATASETS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                **DATASET_READ,
                "code": "ERR.DS_API",
                "message": "ok",
                "dataset_errors": [{"code": "x"}],
            },
        )
    )
    response = _rpc("createDataset", CREATE_BODY)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == DS_ID
    assert "code" not in body
    assert "message" not in body
    assert "dataset_errors" not in body
    sent = json.loads(route.calls[0].request.content)
    assert sent["name"] == "ds1"
    assert sent["workbook_id"] == "wb123wb123wb"
    assert sent["dataset"] == {}


def test_json_lists_create_dataset_and_excludes_editor_chart():
    client = TestClient(create_app())
    paths = client.get("/json/").json()["paths"]
    assert "/rpc/createDataset" in paths
    assert "/rpc/validateDataset" in paths
    assert "/rpc/createEditorChart" not in paths


def test_dataset_to_cloud_keeps_read_fields_and_drops_errors():
    from app.adapters.dataset import dataset_to_cloud

    adapted = dataset_to_cloud(
        {
            "id": DS_ID,
            "dataset": {},
            "name": "ds1",
            "workbook_id": "wb123wb123wb",
            "code": "ERR.DS_API",
            "message": "boom",
            "dataset_errors": [{"code": "x"}],
            "debug": {},
        }
    )
    assert adapted["id"] == DS_ID
    assert adapted["name"] == "ds1"
    assert adapted["dataset"] == {}
    assert adapted["workbook_id"] == "wb123wb123wb"
    assert "code" not in adapted
    assert "message" not in adapted
    assert "dataset_errors" not in adapted
    assert "debug" not in adapted


def test_dataset_to_cloud_fills_direct_mode_from_calc_mode():
    from app.adapters.dataset import dataset_to_cloud
    from app.models.generated import DatasetRead

    adapted = dataset_to_cloud(
        {
            "id": DS_ID,
            "name": "ds1",
            "dataset": {
                "result_schema": [
                    {
                        "title": "Тип",
                        "guid": "field-1",
                        "calc_mode": "direct",
                        "source": "col",
                        "type": "DIMENSION",
                        "valid": True,
                        "value_constraint": None,
                    }
                ]
            },
        }
    )
    field = adapted["dataset"]["result_schema"][0]
    assert field["mode"] == "direct"
    assert field["calc_mode"] == "direct"
    DatasetRead.model_validate(adapted)


@respx.mock
def test_validate_dataset_maps_200():
    _mock_signin()
    respx.post(
        "http://control-api.example:8080/api/v1/datasets/ds123ds123ds1/versions/draft/validators/schema"
    ).mock(return_value=httpx.Response(200, json={
        "id": "ds123ds123ds1",
        "dataset": {},
        "name": "ds1",
        "code": "OK",
        "message": "Validation was successful",
    }))
    response = _rpc("validateDataset", {"datasetId": "ds123ds123ds1", "data": {"dataset": {}}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == "ds123ds123ds1"
    assert "code" not in body


@respx.mock
def test_validate_dataset_200_fills_id_from_args():
    _mock_signin()
    respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={"dataset": {}, "name": "ds1", "options": {}},
        )
    )
    response = _rpc("validateDataset", {"datasetId": DS_ID, "data": {"dataset": {}}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == DS_ID
    assert "dataset" in body


@respx.mock
def test_validate_dataset_400_with_nonempty_dataset_maps_200():
    _mock_signin()
    respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "id": DS_ID,
                "dataset": {"sources": [], "description": "validated"},
                "name": "ds1",
                "code": "ERR.DS_API.VALIDATION",
                "message": "Validation failed",
            },
        )
    )
    response = _rpc("validateDataset", {"datasetId": DS_ID, "data": {"dataset": {}}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == DS_ID
    assert "dataset" in body
    assert body["dataset"]
    assert "code" not in body


@respx.mock
def test_validate_dataset_400_null_dataset_is_invalid_argument():
    _mock_signin()
    respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "id": DS_ID,
                "dataset": None,
                "name": "ds1",
                "code": "ERR.DS_API.VALIDATION",
                "message": "Validation failed",
            },
        )
    )
    response = _rpc("validateDataset", {"datasetId": DS_ID, "data": {"dataset": {}}})
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_ARGUMENT"


@respx.mock
def test_validate_dataset_400_empty_dataset_is_invalid_argument():
    _mock_signin()
    respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "id": DS_ID,
                "dataset": {},
                "name": "ds1",
                "code": "ERR.DS_API.VALIDATION",
                "message": "Validation failed",
            },
        )
    )
    response = _rpc("validateDataset", {"datasetId": DS_ID, "data": {"dataset": {}}})
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_ARGUMENT"


@respx.mock
def test_validate_dataset_400_without_dataset_is_invalid_argument():
    _mock_signin()
    respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(
            400,
            json={"message": "bad schema", "code": "ERR.DS_API"},
        )
    )
    response = _rpc("validateDataset", {"datasetId": DS_ID, "data": {"dataset": {}}})
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["code"] == "INVALID_ARGUMENT"


@respx.mock
def test_validate_dataset_sends_dataset_header_and_workbook_query():
    _mock_signin()
    route = respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc(
        "validateDataset",
        {
            "datasetId": DS_ID,
            "workbookId": "wb123wb123wb",
            "bindedDatasetId": "ds-bind",
            "data": {"dataset": {}},
        },
    )
    assert response.status_code == 200, response.text
    request = route.calls[0].request
    assert request.headers["x-dl-dataset-id"] == "ds-bind"
    assert request.url.params["workbook_id"] == "wb123wb123wb"


@respx.mock
def test_validate_dataset_sends_dataset_id_header_when_no_binded():
    _mock_signin()
    route = respx.post(DATASET_VALIDATE_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc("validateDataset", {"datasetId": DS_ID, "data": {"dataset": {}}})
    assert response.status_code == 200, response.text
    assert route.calls[0].request.headers["x-dl-dataset-id"] == DS_ID


@respx.mock
def test_get_dataset_sends_workbook_id():
    _mock_signin()
    route = respx.get(DATASET_DRAFT_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc(
        "getDataset",
        {"datasetId": DS_ID, "workbookId": "wb123wb123wb", "rev_id": "rev1"},
    )
    assert response.status_code == 200, response.text
    params = route.calls[0].request.url.params
    assert params["workbook_id"] == "wb123wb123wb"
    assert params["rev_id"] == "rev1"


@respx.mock
def test_update_dataset_sends_workbook_id():
    _mock_signin()
    route = respx.put(DATASET_DRAFT_URL).mock(
        return_value=httpx.Response(200, json=DATASET_READ)
    )
    response = _rpc(
        "updateDataset",
        {
            "datasetId": DS_ID,
            "workbookId": "wb123wb123wb",
            "data": {"dataset": {}, "name": "ds2"},
        },
    )
    assert response.status_code == 200, response.text
    assert route.calls[0].request.url.params["workbook_id"] == "wb123wb123wb"
