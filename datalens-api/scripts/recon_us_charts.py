#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

AUTH_HOST = os.environ.get("AUTH_HOST", "http://auth:8080").rstrip("/")
AUTH_LOGIN = os.environ.get("AUTH_LOGIN", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin")
US_HOST = os.environ.get("US_HOST", "http://us:8080").rstrip("/")
US_MASTER_TOKEN = os.environ.get("US_MASTER_TOKEN", "us-master-token")
US_TENANT_ID = os.environ.get("US_TENANT_ID", "common")
RPC_BASE = os.environ.get("DATALENS_API_BASE", "http://127.0.0.1:8393").rstrip("/")
DL_API_TOKEN = os.environ.get("DL_API_TOKEN", "")
OUT = Path(os.environ.get("RECON_OUT", "docs/superpowers/reference/us-charts-recon"))
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

MIN_DASH_DATA = {
    "counter": 1,
    "salt": "recon",
    "schemeVersion": 2,
    "tabs": [{"id": "t1", "title": "Tab", "items": [], "layout": [], "aliases": {}}],
    "settings": {},
}

MIN_WIZARD_DATA = {"shared": {"title": "recon-wizard"}}
MIN_QL_DATA = {"shared": {"title": "recon-ql"}}

WIZARD_TYPES = ("graph_wizard_node", "table_wizard_node")
QL_TYPES = ("ql", "ql_node", "graph_ql_node", "table_ql_node")
DASH_TYPES = ("dash", "")


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
                json={"title": "recon-us-charts", "description": "us charts recon"},
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
            json={"title": "recon-us-charts"},
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


def _private_headers() -> dict[str, str]:
    return {
        "x-us-master-token": US_MASTER_TOKEN,
        "x-dl-tenant-id": US_TENANT_ID,
        "accept": "application/json",
    }


def _jwt_headers(jwt: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {jwt}",
        "x-dl-tenant-id": US_TENANT_ID,
        "accept": "application/json",
    }


def _entry_id(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("entryId", "entry_id", "id"):
        value = body.get(key)
        if value:
            return str(value)
    return None


def _data_stored(body: Any, sent: Any) -> bool:
    if not isinstance(body, dict):
        return False
    stored = body.get("data")
    if stored is None:
        return False
    if sent in (None, {}):
        return stored is not None
    return stored == sent or (isinstance(stored, dict) and bool(stored))


def create_entry(
    us: httpx.Client,
    jwt: str,
    *,
    dump_prefix: str,
    payload: dict[str, Any],
) -> tuple[httpx.Response, str]:
    private = us.post("/private/entries", headers=_private_headers(), json=payload)
    dump(f"{dump_prefix}.private", private)
    if private.status_code < 300:
        return private, "private"
    public = us.post("/v1/entries", headers=_jwt_headers(jwt), json=payload)
    dump(f"{dump_prefix}.public", public)
    return public, "public"


def delete_entry(us: httpx.Client, entry_id: str, dump_name: str) -> None:
    deleted = us.delete(f"/private/entries/{entry_id}", headers=_private_headers())
    dump(dump_name, deleted)
    if deleted.status_code >= 300:
        fallback = us.delete(f"/v1/entries/{entry_id}", headers=_private_headers())
        dump(f"{dump_name}.master-on-public", fallback)


def crud_entry(
    us: httpx.Client,
    jwt: str,
    *,
    kind: str,
    payload: dict[str, Any],
    update_data: dict[str, Any],
    created_ids: list[str],
) -> str | None:
    created, via = create_entry(us, jwt, dump_prefix=f"create{kind}", payload=payload)
    if created.status_code >= 300:
        return None
    body = created.json() or {}
    entry_id = _entry_id(body)
    if not entry_id:
        raise SystemExit(f"create{kind} returned no entryId: {redact(body)}")
    created_ids.append(entry_id)
    print(f"  {kind}: entryId={entry_id} via={via} type={payload.get('type')!r}")
    print(f"  {kind}: data stored on create: {_data_stored(body, payload.get('data'))}")

    get_private = us.get(f"/private/entries/{entry_id}", headers=_private_headers())
    dump(f"get{kind}.private", get_private)
    get_private_v1 = us.get(f"/private/v1/entries/{entry_id}", headers=_private_headers())
    dump(f"get{kind}.private-v1", get_private_v1)
    get_public_master = us.get(f"/v1/entries/{entry_id}", headers=_private_headers())
    dump(f"get{kind}.public-master", get_public_master)
    get_public_jwt = us.get(f"/v1/entries/{entry_id}", headers=_jwt_headers(jwt))
    dump(f"get{kind}.public-jwt", get_public_jwt)
    get_perms = us.get(
        f"/private/entries/{entry_id}",
        headers=_private_headers(),
        params={"includePermissionsInfo": "true", "includeLinks": "true"},
    )
    dump(f"get{kind}.private.perms", get_perms)

    got = get_private.json() if get_private.status_code < 300 else None
    if got is None and get_public_jwt.status_code < 300:
        got = get_public_jwt.json()
    print(f"  {kind}: data stored on get: {_data_stored(got, payload.get('data'))}")

    update_save = us.post(
        f"/private/entries/{entry_id}",
        headers=_private_headers(),
        json={"mode": "save", "data": update_data, "meta": {"recon": "save"}},
    )
    dump(f"update{kind}.save", update_save)
    update_publish = us.post(
        f"/private/entries/{entry_id}",
        headers=_private_headers(),
        json={"mode": "publish", "data": update_data, "meta": {"recon": "publish"}},
    )
    dump(f"update{kind}.publish", update_publish)
    update_v1 = us.post(
        f"/private/v1/entries/{entry_id}",
        headers=_private_headers(),
        json={"mode": "save", "data": update_data},
    )
    dump(f"update{kind}.private-v1", update_v1)

    delete_entry(us, entry_id, f"delete{kind}.private")
    if entry_id in created_ids:
        created_ids.remove(entry_id)
    return entry_id


def main() -> None:
    workbook_id: str | None = None
    created_ids: list[str] = []
    jwt = ""
    try:
        with httpx.Client(timeout=30.0) as auth_client:
            jwt = signin(auth_client)
        workbook_id = create_workbook()
        with httpx.Client(base_url=US_HOST, timeout=30.0) as us:
            dash_ok = False
            for dash_type in DASH_TYPES:
                label = dash_type if dash_type else "empty"
                payload = {
                    "scope": "dash",
                    "type": dash_type,
                    "workbookId": workbook_id,
                    "name": f"recon-dash-{label}",
                    "data": MIN_DASH_DATA,
                    "meta": {},
                }
                created, via = create_entry(
                    us, jwt, dump_prefix=f"createDash.type-{label}", payload=payload
                )
                if created.status_code >= 300:
                    continue
                dash_ok = True
                body = created.json() or {}
                entry_id = _entry_id(body)
                if not entry_id:
                    raise SystemExit(f"createDash returned no entryId: {redact(body)}")
                created_ids.append(entry_id)
                print(f"  dash: entryId={entry_id} via={via} type={dash_type!r}")
                print(f"  dash: data stored on create: {_data_stored(body, MIN_DASH_DATA)}")
                get_private = us.get(f"/private/entries/{entry_id}", headers=_private_headers())
                dump("getDash.private", get_private)
                dump(
                    "getDash.private-v1",
                    us.get(f"/private/v1/entries/{entry_id}", headers=_private_headers()),
                )
                dump(
                    "getDash.public-master",
                    us.get(f"/v1/entries/{entry_id}", headers=_private_headers()),
                )
                dump(
                    "getDash.public-jwt",
                    us.get(f"/v1/entries/{entry_id}", headers=_jwt_headers(jwt)),
                )
                dump(
                    "getDash.private.perms",
                    us.get(
                        f"/private/entries/{entry_id}",
                        headers=_private_headers(),
                        params={
                            "includePermissionsInfo": "true",
                            "includeLinks": "true",
                            "branch": "saved",
                        },
                    ),
                )
                got = get_private.json() if get_private.status_code < 300 else None
                print(f"  dash: data stored on get: {_data_stored(got, MIN_DASH_DATA)}")
                updated = dict(MIN_DASH_DATA)
                updated["salt"] = "recon-updated"
                dump(
                    "updateDash.save",
                    us.post(
                        f"/private/entries/{entry_id}",
                        headers=_private_headers(),
                        json={"mode": "save", "data": updated, "meta": {"recon": "save"}},
                    ),
                )
                dump(
                    "updateDash.publish",
                    us.post(
                        f"/private/entries/{entry_id}",
                        headers=_private_headers(),
                        json={"mode": "publish", "data": updated, "meta": {"recon": "publish"}},
                    ),
                )
                dump(
                    "updateDash.private-v1",
                    us.post(
                        f"/private/v1/entries/{entry_id}",
                        headers=_private_headers(),
                        json={"mode": "save", "data": updated},
                    ),
                )
                delete_entry(us, entry_id, "deleteDash.private")
                if entry_id in created_ids:
                    created_ids.remove(entry_id)
                break
            if not dash_ok:
                print("  dash: all type attempts failed")
            empty_payload = {
                "scope": "dash",
                "type": "",
                "workbookId": workbook_id,
                "name": "recon-dash-empty-type",
                "data": MIN_DASH_DATA,
                "meta": {},
            }
            empty_created, empty_via = create_entry(
                us, jwt, dump_prefix="createDash.type-empty", payload=empty_payload
            )
            if empty_created.status_code < 300:
                empty_id = _entry_id(empty_created.json() or {})
                if empty_id:
                    created_ids.append(empty_id)
                    print(f"  dash type='': entryId={empty_id} via={empty_via}")
                    dump(
                        "getDash.type-empty.private",
                        us.get(f"/private/entries/{empty_id}", headers=_private_headers()),
                    )
                    delete_entry(us, empty_id, "deleteDash.type-empty.private")
                    if empty_id in created_ids:
                        created_ids.remove(empty_id)

            for wizard_type in WIZARD_TYPES:
                suffix = wizard_type.replace("_wizard_node", "")
                payload = {
                    "scope": "widget",
                    "type": wizard_type,
                    "workbookId": workbook_id,
                    "name": f"recon-wizard-{suffix}",
                    "data": MIN_WIZARD_DATA,
                    "meta": {},
                }
                if wizard_type == "graph_wizard_node":
                    crud_entry(
                        us,
                        jwt,
                        kind="WizardGraph",
                        payload=payload,
                        update_data={"shared": {"title": "recon-wizard-updated"}},
                        created_ids=created_ids,
                    )
                else:
                    created, via = create_entry(
                        us, jwt, dump_prefix=f"createWizard.{suffix}", payload=payload
                    )
                    if created.status_code < 300:
                        entry_id = _entry_id(created.json() or {})
                        if entry_id:
                            created_ids.append(entry_id)
                            print(f"  wizard {wizard_type}: entryId={entry_id} via={via}")
                            dump(
                                f"getWizard.{suffix}.private",
                                us.get(f"/private/entries/{entry_id}", headers=_private_headers()),
                            )
                            delete_entry(us, entry_id, f"deleteWizard.{suffix}.private")
                            if entry_id in created_ids:
                                created_ids.remove(entry_id)

            ql_ok = False
            for ql_type in QL_TYPES:
                payload = {
                    "scope": "widget",
                    "type": ql_type,
                    "workbookId": workbook_id,
                    "name": f"recon-ql-{ql_type}",
                    "data": MIN_QL_DATA,
                    "meta": {},
                }
                if not ql_ok:
                    entry_id = crud_entry(
                        us,
                        jwt,
                        kind=f"QL.{ql_type}",
                        payload=payload,
                        update_data={"shared": {"title": "recon-ql-updated"}},
                        created_ids=created_ids,
                    )
                    if entry_id:
                        ql_ok = True
                else:
                    created, via = create_entry(
                        us, jwt, dump_prefix=f"createQL.{ql_type}", payload=payload
                    )
                    if created.status_code < 300:
                        entry_id = _entry_id(created.json() or {})
                        if entry_id:
                            created_ids.append(entry_id)
                            print(f"  ql extra {ql_type}: entryId={entry_id} via={via}")
                            delete_entry(us, entry_id, f"deleteQL.{ql_type}.private")
                            if entry_id in created_ids:
                                created_ids.remove(entry_id)
            if not ql_ok:
                print("  ql: all type attempts failed")
    finally:
        if created_ids:
            with httpx.Client(base_url=US_HOST, timeout=30.0) as us:
                for entry_id in list(created_ids):
                    delete_entry(us, entry_id, f"cleanup.entry.{entry_id}")
        if workbook_id:
            delete_workbook(workbook_id)


if __name__ == "__main__":
    main()
