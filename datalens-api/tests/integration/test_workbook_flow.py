# datalens-api/tests/integration/test_workbook_flow.py
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


def test_workbook_crud_roundtrip():
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        created = client.post(
            "/rpc/createWorkbook",
            headers=HEADERS,
            json={"title": "itest-wb", "description": "integration"},
        )
        assert created.status_code == 200, created.text
        workbook_id = created.json()["workbookId"]

        listed = client.post(
            "/rpc/getWorkbooksList",
            headers=HEADERS,
            json={"filterString": "itest-wb", "page": 0, "pageSize": 50},
        )
        assert listed.status_code == 200
        ids = [w["workbookId"] for w in listed.json()["workbooks"]]
        assert workbook_id in ids

        deleted = client.post(
            "/rpc/deleteWorkbook",
            headers=HEADERS,
            json={"workbookId": workbook_id},
        )
        assert deleted.status_code == 200
