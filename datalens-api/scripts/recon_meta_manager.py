#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

META_MANAGER_HOST = os.environ.get("META_MANAGER_HOST", "http://meta-manager:8080").rstrip("/")
AUTH_HOST = os.environ.get("AUTH_HOST", "http://auth:8080").rstrip("/")
AUTH_LOGIN = os.environ.get("AUTH_LOGIN", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin")
US_HOST = os.environ.get("US_HOST", "http://us:8080").rstrip("/")
US_MASTER_TOKEN = os.environ.get("US_MASTER_TOKEN", "us-master-token")
US_TENANT_ID = os.environ.get("US_TENANT_ID", "common")
RPC_BASE = os.environ.get("DATALENS_API_BASE", "http://127.0.0.1:8393").rstrip("/")
DL_API_TOKEN = os.environ.get("DL_API_TOKEN", "")
OUT = Path(os.environ.get("RECON_OUT", "docs/superpowers/reference/meta-manager-recon"))
OUT.mkdir(parents=True, exist_ok=True)

POLL_SECONDS = float(os.environ.get("RECON_POLL_SECONDS", "60"))
POLL_STEP = float(os.environ.get("RECON_POLL_STEP", "1"))

_REDACT_KEYS = {
    "password",
    "ssl_ca",
    "accesstoken",
    "refreshtoken",
    "authorization",
    "cookie",
    "set-cookie",
    "us_master_token",
    "x-us-master-token",
    "hash",
}


def _is_secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _REDACT_KEYS:
        return True
    return any(part in lowered for part in ("password", "token", "secret", "ssl_ca"))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if _is_secret_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", value):
        return "***REDACTED_JWT***"
    return value


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _request_body(response: httpx.Response) -> Any:
    content = response.request.content
    if not content:
        return None
    try:
        return json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return content.decode("utf-8", errors="replace")


def dump(name: str, response: httpx.Response) -> None:
    payload = redact(
        {
            "url": str(response.request.url),
            "method": response.request.method,
            "status": response.status_code,
            "headers_sent": dict(response.request.headers),
            "request_body": _request_body(response),
            "body": _safe_json(response),
        }
    )
    (OUT / f"{name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"{name}: {response.status_code} {response.request.method} {response.request.url}")


def _token_from_cookie_value(raw: str) -> str | None:
    for candidate in (raw, unquote(raw)):
        try:
            data: Any = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("accessToken"):
            return str(data["accessToken"])
    return None


def signin(client: httpx.Client) -> str:
    response = client.post(
        f"{AUTH_HOST}/signin",
        json={"login": AUTH_LOGIN, "password": AUTH_PASSWORD},
    )
    dump("signin", response)
    if response.status_code >= 400:
        raise SystemExit(f"signin failed: {response.status_code}")
    cookie = response.cookies.get("auth")
    if cookie:
        token = _token_from_cookie_value(cookie)
        if token:
            return token
    try:
        body: Any = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and body.get("accessToken"):
        return str(body["accessToken"])
    raise SystemExit("signin did not return accessToken")


def create_workbook(title: str, description: str) -> str:
    if DL_API_TOKEN:
        with httpx.Client(base_url=RPC_BASE, timeout=30.0) as rpc:
            created = rpc.post(
                "/rpc/createWorkbook",
                headers={
                    "Authorization": f"Bearer {DL_API_TOKEN}",
                    "x-dl-api-version": "2",
                    "Content-Type": "application/json",
                },
                json={"title": title, "description": description},
            )
            dump("createWorkbook.rpc", created)
            if created.status_code < 300:
                workbook_id = (created.json() or {}).get("workbookId")
                if workbook_id:
                    return str(workbook_id)
    with httpx.Client(base_url=US_HOST, timeout=30.0) as us:
        created = us.post(
            "/private/v2/workbooks",
            headers={
                "x-us-master-token": US_MASTER_TOKEN,
                "x-dl-tenant-id": US_TENANT_ID,
                "accept": "application/json",
            },
            json={"title": title},
        )
        dump("createWorkbook.us", created)
        if created.status_code >= 300:
            raise SystemExit(f"createWorkbook failed: {created.status_code}")
        workbook_id = (created.json() or {}).get("workbookId")
        if not workbook_id:
            raise SystemExit("createWorkbook returned no workbookId")
        return str(workbook_id)


def delete_workbook(workbook_id: str, dump_name: str) -> None:
    if DL_API_TOKEN:
        with httpx.Client(base_url=RPC_BASE, timeout=30.0) as rpc:
            deleted = rpc.post(
                "/rpc/deleteWorkbook",
                headers={
                    "Authorization": f"Bearer {DL_API_TOKEN}",
                    "x-dl-api-version": "2",
                    "Content-Type": "application/json",
                },
                json={"workbookId": workbook_id},
            )
            dump(dump_name, deleted)
            if deleted.status_code < 300:
                return
    with httpx.Client(base_url=US_HOST, timeout=30.0) as us:
        deleted = us.delete(
            f"/private/v2/workbooks/{workbook_id}",
            headers={
                "x-us-master-token": US_MASTER_TOKEN,
                "x-dl-tenant-id": US_TENANT_ID,
                "accept": "application/json",
            },
        )
        dump(f"{dump_name}.us", deleted)


def _body_dict(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _summarize_export_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"type": type(data).__name__}
    export = data.get("export")
    entries_keys: list[str] = []
    version = None
    if isinstance(export, dict):
        version = export.get("version")
        entries = export.get("entries")
        if isinstance(entries, dict):
            entries_keys = sorted(str(key) for key in entries)
    return {
        "top_keys": sorted(str(key) for key in data),
        "export.version": version,
        "export.entries.scopes": entries_keys,
        "has_hash": "hash" in data,
    }


def poll_until(
    client: httpx.Client,
    path: str,
    headers: dict[str, str],
    *,
    dump_pending: str,
    dump_final: str,
) -> httpx.Response:
    deadline = time.monotonic() + POLL_SECONDS
    dumped_pending = False
    last: httpx.Response | None = None
    while time.monotonic() < deadline:
        last = client.get(path, headers=headers)
        body = _body_dict(last)
        status = body.get("status")
        print(f"  poll {path}: http={last.status_code} status={status!r} progress={body.get('progress')!r}")
        if last.status_code >= 400:
            dump(dump_final, last)
            return last
        if status in {"success", "error"}:
            dump(dump_final, last)
            return last
        if status == "pending" and not dumped_pending:
            dump(dump_pending, last)
            dumped_pending = True
        time.sleep(POLL_STEP)
    if last is None:
        raise SystemExit(f"poll {path}: no response")
    dump(dump_final, last)
    print(f"  poll {path}: timeout after {POLL_SECONDS}s, last status={_body_dict(last).get('status')!r}")
    return last


def main() -> None:
    source_workbook_id: str | None = None
    imported_workbook_id: str | None = None
    jwt = ""
    in_flight_export_ids: list[str] = []
    try:
        with httpx.Client(timeout=30.0) as auth_client:
            jwt = signin(auth_client)
        source_workbook_id = create_workbook("recon-meta-manager", "meta-manager recon")
        jwt_headers = {
            "Authorization": f"Bearer {jwt}",
            "accept": "application/json",
            "x-request-id": "recon-meta-manager",
        }
        with httpx.Client(base_url=META_MANAGER_HOST, timeout=60.0) as client:
            noauth = client.post(
                "/workbooks/export",
                json={"workbookId": source_workbook_id},
            )
            dump("startExport.noauth", noauth)
            if noauth.status_code < 300:
                export_id = _body_dict(noauth).get("exportId")
                if export_id:
                    in_flight_export_ids.append(str(export_id))
                print("  auth: start without JWT succeeded — JWT not required on this hit")
            elif noauth.status_code == 401:
                print("  auth: start without JWT → 401")
            else:
                print(f"  auth: start without JWT → {noauth.status_code}")

            started = client.post(
                "/workbooks/export",
                headers=jwt_headers,
                json={"workbookId": source_workbook_id},
            )
            dump("startExport", started)
            if started.status_code == 401:
                print("  auth: start with JWT → 401, retrying without Authorization")
                started = client.post(
                    "/workbooks/export",
                    json={"workbookId": source_workbook_id},
                )
                dump("startExport.unauth-fallback", started)
            if started.status_code >= 300:
                raise SystemExit(f"startExport failed: {started.status_code}")
            export_id = _body_dict(started).get("exportId")
            if not export_id:
                raise SystemExit(f"startExport returned no exportId: {redact(_body_dict(started))}")
            export_id = str(export_id)
            in_flight_export_ids.append(export_id)
            print(f"  exportId={export_id}")

            auth_headers = jwt_headers if started.request.headers.get("authorization") else {}
            before = client.get(f"/workbooks/export/{export_id}/result", headers=auth_headers)
            dump("getExportResult.before-success", before)
            print(
                f"  getResult-before-success: http={before.status_code} "
                f"body_keys={sorted(_body_dict(before))}"
            )

            status_resp = poll_until(
                client,
                f"/workbooks/export/{export_id}",
                auth_headers,
                dump_pending="getExportStatus.pending",
                dump_final="getExportStatus",
            )
            export_status = _body_dict(status_resp).get("status")
            if export_status == "success":
                in_flight_export_ids = [item for item in in_flight_export_ids if item != export_id]

            result = client.get(f"/workbooks/export/{export_id}/result", headers=auth_headers)
            dump("getExportResult", result)
            result_body = _body_dict(result)
            print(f"  getResult: http={result.status_code} {_summarize_export_data(result_body.get('data'))}")
            if result.status_code >= 300:
                raise SystemExit(f"getExportResult failed: {result.status_code}")
            data = result_body.get("data")
            if not isinstance(data, dict):
                raise SystemExit(f"getExportResult data is not an object: {redact(result_body)}")

            imported = client.post(
                "/workbooks/import",
                headers=auth_headers,
                json={
                    "title": "recon-meta-manager-imported",
                    "description": "meta-manager recon import",
                    "data": data,
                },
            )
            dump("startImport", imported)
            if imported.status_code >= 300:
                raise SystemExit(f"startImport failed: {imported.status_code}")
            import_body = _body_dict(imported)
            import_id = import_body.get("importId")
            imported_workbook_id = import_body.get("workbookId")
            if imported_workbook_id:
                imported_workbook_id = str(imported_workbook_id)
            if not import_id:
                raise SystemExit(f"startImport returned no importId: {redact(import_body)}")
            import_id = str(import_id)
            print(f"  importId={import_id} workbookId={imported_workbook_id}")

            poll_until(
                client,
                f"/workbooks/import/{import_id}",
                auth_headers,
                dump_pending="getImportStatus.pending",
                dump_final="getImportStatus",
            )

            cancel_started = client.post(
                "/workbooks/export",
                headers=auth_headers,
                json={"workbookId": source_workbook_id},
            )
            dump("startExport.for-cancel", cancel_started)
            cancel_id = _body_dict(cancel_started).get("exportId")
            if cancel_started.status_code < 300 and cancel_id:
                cancel_id = str(cancel_id)
                in_flight_export_ids.append(cancel_id)
                cancelled = client.post(
                    f"/workbooks/export/{cancel_id}/cancel",
                    headers=auth_headers,
                )
                dump("cancelExport", cancelled)
                if cancelled.status_code < 300:
                    in_flight_export_ids = [
                        item for item in in_flight_export_ids if item != cancel_id
                    ]
            else:
                print(f"  cancel: could not start second export: {cancel_started.status_code}")
    finally:
        if in_flight_export_ids and jwt:
            with httpx.Client(base_url=META_MANAGER_HOST, timeout=30.0) as client:
                for export_id in list(in_flight_export_ids):
                    cancelled = client.post(
                        f"/workbooks/export/{export_id}/cancel",
                        headers={
                            "Authorization": f"Bearer {jwt}",
                            "accept": "application/json",
                        },
                    )
                    dump(f"cancelExport.cleanup.{export_id}", cancelled)
        if imported_workbook_id:
            delete_workbook(imported_workbook_id, "deleteWorkbook.imported.rpc")
        if source_workbook_id:
            delete_workbook(source_workbook_id, "deleteWorkbook.rpc")


if __name__ == "__main__":
    main()
