#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

US_HOST = os.environ.get("US_HOST", "http://127.0.0.1:8081").rstrip("/")
TOKEN = os.environ.get("US_MASTER_TOKEN", "us-master-token")
TENANT = os.environ.get("US_TENANT_ID", "common")
OUT = Path(os.environ.get("RECON_OUT", "docs/superpowers/reference/us-recon"))
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "x-us-master-token": TOKEN,
    "x-dl-tenant-id": TENANT,
    "accept": "application/json",
}


def dump(name: str, response: httpx.Response) -> None:
    payload = {
        "url": str(response.request.url),
        "status": response.status_code,
        "headers_sent": dict(response.request.headers),
        "body": _safe_json(response),
    }
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"{name}: {response.status_code} {response.request.url}")


def _safe_json(response: httpx.Response):
    try:
        return response.json()
    except ValueError:
        return response.text


def main() -> None:
    with httpx.Client(base_url=US_HOST, headers=HEADERS, timeout=30.0) as client:
        listed = client.get("/v2/workbooks", params={"page": 0, "pageSize": 10})
        dump("getWorkbooksList", listed)
        if listed.status_code == 401:
            private = client.get("/private/v2/workbooks/does-not-exist")
            dump("privateGetWorkbook_probe", private)
            raise SystemExit(
                "Публичный /v2/workbooks вернул 401. "
                "Зафиксируйте это в README recon и переключите клиент на JWT/private."
            )
        created = client.post("/v2/workbooks", json={"title": "recon-wb"})
        dump("createWorkbook", created)
        workbook_id = (created.json() or {}).get("workbookId") if created.status_code < 300 else None
        if workbook_id:
            dump("getWorkbook", client.get(f"/v2/workbooks/{workbook_id}"))
            dump(
                "getWorkbookEntries",
                client.get(f"/v2/workbooks/{workbook_id}/entries", params={"page": 0, "pageSize": 10}),
            )
            dump("deleteWorkbook", client.delete(f"/v2/workbooks/{workbook_id}"))
        dump(
            "getStructureItems",
            client.get("/v1/structure-items", params={"page": 0, "pageSize": 10}),
        )
        dump("getRootCollectionPermissions", client.get("/v1/root-collection-permissions"))


if __name__ == "__main__":
    main()
