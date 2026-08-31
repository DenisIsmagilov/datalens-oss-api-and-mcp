import os

import httpx
import pytest

pytestmark = pytest.mark.integration

BASE = os.environ.get("DATALENS_API_BASE", "http://127.0.0.1:8393")
TOKEN = os.environ["DL_API_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "x-dl-api-version": "2",
    "Content-Type": "application/json",
}


def _rpc(client: httpx.Client, method: str, payload: dict) -> httpx.Response:
    return client.post(f"/rpc/{method}", headers=HEADERS, json=payload)


def _cleanup(
    client: httpx.Client,
    *,
    dataset_id: str | None,
    connection_id: str | None,
    workbook_id: str | None,
) -> None:
    if dataset_id:
        _rpc(client, "deleteDataset", {"datasetId": dataset_id})
    if connection_id:
        _rpc(client, "deleteConnection", {"connectionId": connection_id})
    if workbook_id:
        _rpc(client, "deleteWorkbook", {"workbookId": workbook_id})


def test_connection_dataset_crud_roundtrip():
    workbook_id = None
    connection_id = None
    dataset_id = None
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        try:
            created_wb = _rpc(client, "createWorkbook", {"title": "itest-bi"})
            assert created_wb.status_code == 200, created_wb.text
            workbook_id = created_wb.json()["workbookId"]

            created_conn = _rpc(
                client,
                "createConnection",
                {
                    "type": "clickhouse",
                    "name": "itest-ch",
                    "host": "127.0.0.1",
                    "port": 8123,
                    "username": "default",
                    "password": "x",
                    "secure": "off",
                    "workbook_id": workbook_id,
                    "dir_path": "/",
                },
            )
            assert created_conn.status_code == 200, created_conn.text
            connection_id = created_conn.json()["id"]
            assert connection_id

            got_conn = _rpc(client, "getConnection", {"connectionId": connection_id})
            assert got_conn.status_code == 200, got_conn.text
            conn_body = got_conn.json()
            assert conn_body["id"] == connection_id
            assert conn_body.get("type") == "clickhouse"

            created_ds = _rpc(
                client,
                "createDataset",
                {
                    "name": "itest-ds",
                    "workbook_id": workbook_id,
                    "dataset": {},
                },
            )
            assert created_ds.status_code == 200, created_ds.text
            dataset_id = created_ds.json()["id"]
            assert dataset_id

            got_ds = _rpc(client, "getDataset", {"datasetId": dataset_id})
            assert got_ds.status_code == 200, got_ds.text
            assert got_ds.json()["id"] == dataset_id

            validated = _rpc(
                client,
                "validateDataset",
                {"datasetId": dataset_id, "data": {"dataset": {}}},
            )
            assert validated.status_code in (200, 400), validated.text
            if validated.status_code == 200:
                body = validated.json()
                assert body.get("id")
                assert "dataset" in body
            else:
                body = validated.json()
                assert "code" in body
                assert "message" in body
                assert "details" in body

            deleted_ds = _rpc(client, "deleteDataset", {"datasetId": dataset_id})
            assert deleted_ds.status_code == 200, deleted_ds.text
            dataset_id = None

            deleted_conn = _rpc(
                client, "deleteConnection", {"connectionId": connection_id}
            )
            assert deleted_conn.status_code == 200, deleted_conn.text
            connection_id = None

            deleted_wb = _rpc(client, "deleteWorkbook", {"workbookId": workbook_id})
            assert deleted_wb.status_code == 200, deleted_wb.text
            workbook_id = None
        finally:
            _cleanup(
                client,
                dataset_id=dataset_id,
                connection_id=connection_id,
                workbook_id=workbook_id,
            )
