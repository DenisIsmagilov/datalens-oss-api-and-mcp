#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

CONTROL_API_HOST = os.environ.get("CONTROL_API_HOST", "http://control-api:8080").rstrip("/")
AUTH_HOST = os.environ.get("AUTH_HOST", "http://auth:8080").rstrip("/")
AUTH_LOGIN = os.environ.get("AUTH_LOGIN", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin")
US_HOST = os.environ.get("US_HOST", "http://us:8080").rstrip("/")
US_MASTER_TOKEN = os.environ.get("US_MASTER_TOKEN", "us-master-token")
US_TENANT_ID = os.environ.get("US_TENANT_ID", "common")
RPC_BASE = os.environ.get("DATALENS_API_BASE", "http://127.0.0.1:8393").rstrip("/")
DL_API_TOKEN = os.environ.get("DL_API_TOKEN", "")
OUT = Path(os.environ.get("RECON_OUT", "docs/superpowers/reference/control-api-recon"))
OUT.mkdir(parents=True, exist_ok=True)

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


def dump(name: str, response: httpx.Response) -> None:
    payload = redact(
        {
            "url": str(response.request.url),
            "method": response.request.method,
            "status": response.status_code,
            "headers_sent": dict(response.request.headers),
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


def create_workbook() -> str:
    if DL_API_TOKEN:
        with httpx.Client(base_url=RPC_BASE, timeout=30.0) as rpc:
            created = rpc.post(
                "/rpc/createWorkbook",
                headers={
                    "Authorization": f"Bearer {DL_API_TOKEN}",
                    "x-dl-api-version": "2",
                    "Content-Type": "application/json",
                },
                json={"title": "recon-control-api", "description": "control-api recon"},
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
            json={"title": "recon-control-api"},
        )
        dump("createWorkbook.us", created)
        if created.status_code >= 300:
            raise SystemExit(f"createWorkbook failed: {created.status_code}")
        workbook_id = (created.json() or {}).get("workbookId")
        if not workbook_id:
            raise SystemExit("createWorkbook returned no workbookId")
        return str(workbook_id)


def delete_workbook(workbook_id: str) -> None:
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
            dump("deleteWorkbook.rpc", deleted)
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
        dump("deleteWorkbook.us", deleted)


def _connection_payloads(workbook_id: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "clickhouse",
            {
                "type": "clickhouse",
                "name": "recon-ch",
                "host": "ch.invalid.example",
                "port": 8443,
                "username": "default",
                "password": "x",
                "secure": "on",
                "workbook_id": workbook_id,
                "dir_path": "/",
            },
        ),
        (
            "postgres",
            {
                "type": "postgres",
                "name": "recon-pg",
                "host": "pg.invalid.example",
                "port": 5432,
                "db_name": "db",
                "username": "user",
                "password": "x",
                "workbook_id": workbook_id,
                "dir_path": "/",
            },
        ),
    ]


def main() -> None:
    workbook_id: str | None = None
    connection_id: str | None = None
    jwt = ""
    try:
        with httpx.Client(timeout=30.0) as auth_client:
            jwt = signin(auth_client)
        headers = {
            "Authorization": f"Bearer {jwt}",
            "accept": "application/json",
            "x-request-id": "recon-control-api",
        }
        with httpx.Client(base_url=CONTROL_API_HOST, headers=headers, timeout=30.0) as client:
            dump("infoConnectors", client.get("/api/v1/info/connectors"))
            dump(
                "getDatasetDraftMissing",
                client.get("/api/v1/datasets/doesnotexist1/versions/draft"),
            )
            workbook_id = create_workbook()
            created = None
            for kind, payload in _connection_payloads(workbook_id):
                created = client.post("/api/v1/connections/", json=payload)
                dump(f"createConnection.{kind}", created)
                if created.status_code < 300:
                    break
            if created is None or created.status_code >= 300:
                raise SystemExit("createConnection failed for clickhouse and postgres")
            body = created.json() or {}
            connection_id = body.get("id") or body.get("connection_id") or body.get("entryId")
            if not connection_id:
                raise SystemExit(f"createConnection returned no id: {redact(body)}")
            dump("getConnection", client.get(f"/api/v1/connections/{connection_id}"))
            dump(
                "deleteConnection",
                client.delete(f"/api/v1/connections/{connection_id}"),
            )
            connection_id = None
    finally:
        if connection_id and jwt:
            with httpx.Client(
                base_url=CONTROL_API_HOST,
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "accept": "application/json",
                },
                timeout=30.0,
            ) as client:
                dump(
                    "deleteConnection.cleanup",
                    client.delete(f"/api/v1/connections/{connection_id}"),
                )
        if workbook_id:
            delete_workbook(workbook_id)


if __name__ == "__main__":
    main()
