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


def test_collection_workbook_crud_roundtrip():
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        collection = client.post(
            "/rpc/createCollection",
            headers=HEADERS,
            json={
                "title": "itest-col",
                "description": "integration",
                "parentId": None,
            },
        )
        assert collection.status_code == 200, collection.text
        collection_id = collection.json()["collectionId"]

        created = client.post(
            "/rpc/createWorkbook",
            headers=HEADERS,
            json={
                "title": "itest-wb-col",
                "description": "integration",
                "collectionId": collection_id,
            },
        )
        assert created.status_code == 200, created.text
        workbook_id = created.json()["workbookId"]

        listed = client.post(
            "/rpc/getWorkbooksList",
            headers=HEADERS,
            json={
                "filterString": "itest-wb-col",
                "collectionId": collection_id,
                "page": 0,
                "pageSize": 50,
            },
        )
        assert listed.status_code == 200, listed.text
        ids = [w["workbookId"] for w in listed.json()["workbooks"]]
        assert workbook_id in ids

        entries = client.post(
            "/rpc/getWorkbookEntries",
            headers=HEADERS,
            json={"workbookId": workbook_id, "page": 0, "pageSize": 50},
        )
        assert entries.status_code == 200, entries.text
        assert "entries" in entries.json()

        deleted_wb = client.post(
            "/rpc/deleteWorkbook",
            headers=HEADERS,
            json={"workbookId": workbook_id},
        )
        assert deleted_wb.status_code == 200, deleted_wb.text

        deleted_col = client.post(
            "/rpc/deleteCollection",
            headers=HEADERS,
            json={"collectionId": collection_id},
        )
        assert deleted_col.status_code == 200, deleted_col.text
