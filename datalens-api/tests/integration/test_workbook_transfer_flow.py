import os
import time

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

POLL_SECONDS = 60.0
POLL_STEP = 1.0


def _rpc(client: httpx.Client, method: str, payload: dict) -> httpx.Response:
    return client.post(f"/rpc/{method}", headers=HEADERS, json=payload)


def _poll_status(
    client: httpx.Client, method: str, payload: dict, *, what: str
) -> dict:
    deadline = time.monotonic() + POLL_SECONDS
    last: httpx.Response | None = None
    while time.monotonic() < deadline:
        last = _rpc(client, method, payload)
        assert last.status_code == 200, last.text
        body = last.json()
        status = body.get("status")
        if status == "success":
            return body
        assert status != "error", f"{what} failed: {body}"
        time.sleep(POLL_STEP)
    assert last is not None, f"{what}: no status response"
    raise AssertionError(
        f"{what}: timeout after {POLL_SECONDS}s, last={last.json()}"
    )


def test_workbook_export_import_roundtrip():
    source_workbook_id = None
    imported_workbook_id = None
    with httpx.Client(base_url=BASE, timeout=60.0) as client:
        try:
            created = _rpc(client, "createWorkbook", {"title": "itest-transfer-src"})
            assert created.status_code == 200, created.text
            source_workbook_id = created.json()["workbookId"]
            assert source_workbook_id

            started = _rpc(
                client, "startWorkbookExport", {"workbookId": source_workbook_id}
            )
            assert started.status_code == 200, started.text
            export_id = started.json()["exportId"]
            assert export_id

            export_status = _poll_status(
                client,
                "getWorkbookExportStatus",
                {"exportId": export_id},
                what="export",
            )
            assert export_status["exportId"] == export_id

            result = _rpc(client, "getWorkbookExportResult", {"exportId": export_id})
            assert result.status_code == 200, result.text
            result_body = result.json()
            data = result_body["data"]
            assert "export" in data
            assert "hash" in data
            assert isinstance(data["export"], dict)
            assert isinstance(data["hash"], str)
            assert data["hash"]

            imported = _rpc(
                client,
                "startWorkbookImport",
                {
                    "title": "itest-transfer-dst",
                    "collectionId": None,
                    "data": data,
                },
            )
            assert imported.status_code == 200, imported.text
            import_id = imported.json()["importId"]
            imported_workbook_id = imported.json()["workbookId"]
            assert import_id
            assert imported_workbook_id
            assert imported_workbook_id != source_workbook_id

            import_status = _poll_status(
                client,
                "getWorkbookImportStatus",
                {"importId": import_id},
                what="import",
            )
            assert import_status["importId"] == import_id
            assert import_status["workbookId"] == imported_workbook_id

            deleted_src = _rpc(
                client, "deleteWorkbook", {"workbookId": source_workbook_id}
            )
            assert deleted_src.status_code == 200, deleted_src.text
            source_workbook_id = None

            deleted_dst = _rpc(
                client, "deleteWorkbook", {"workbookId": imported_workbook_id}
            )
            assert deleted_dst.status_code == 200, deleted_dst.text
            imported_workbook_id = None
        finally:
            if source_workbook_id:
                _rpc(client, "deleteWorkbook", {"workbookId": source_workbook_id})
            if imported_workbook_id:
                _rpc(client, "deleteWorkbook", {"workbookId": imported_workbook_id})
