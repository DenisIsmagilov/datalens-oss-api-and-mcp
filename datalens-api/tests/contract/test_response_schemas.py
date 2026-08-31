import json
from pathlib import Path

import jsonschema

SPEC = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "app/models/openapi.prepared.json"
    ).read_text()
)


def _resolve_openapi_union(schema: dict, payload: dict) -> dict:
    """OpenAPI oneOf wrappers (ConnectionRead) have additionalProperties:false
    and empty properties; Draft JSON Schema rejects every real object.
    Resolve via discriminator, otherwise validate oneOf only.
    """
    if not (
        schema.get("oneOf")
        and schema.get("additionalProperties") is False
        and not schema.get("properties")
    ):
        return schema
    discriminator = schema.get("discriminator") or {}
    property_name = discriminator.get("propertyName")
    mapping = discriminator.get("mapping") or {}
    key = payload.get(property_name) if property_name else None
    if key in mapping:
        name = mapping[key].rsplit("/", 1)[-1]
        return SPEC["components"]["schemas"][name]
    return {"oneOf": schema["oneOf"]}


def validate_schema(schema_name: str, payload: dict) -> None:
    schema = _resolve_openapi_union(SPEC["components"]["schemas"][schema_name], payload)
    resolver = jsonschema.RefResolver.from_schema(SPEC)
    jsonschema.validate(payload, schema, resolver=resolver)


def test_empty_workbooks_list_matches_cloud_schema():
    validate_schema("GetWorkbooksListResult", {"workbooks": []})


CREATE_WORKBOOK_RESULT = {
    "workbookId": "abc123abc123a",
    "collectionId": None,
    "title": "T",
    "description": None,
    "tenantId": "common",
    "meta": {},
    "createdBy": "admin",
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedBy": "admin",
    "updatedAt": "2026-01-01T00:00:00.000Z",
    "status": "active",
    "operation": {
        "id": "abc123abc123a",
        "description": "Datalens operation",
        "createdBy": "admin",
        "createdAt": {"seconds": "1767225600"},
        "modifiedAt": {"seconds": "1767225600"},
        "metadata": {},
        "done": True,
    },
}


def test_create_workbook_result_matches_cloud_schema():
    validate_schema("CreateWorkbookResult", CREATE_WORKBOOK_RESULT)


def test_synthesized_create_workbook_matches_cloud_schema():
    from app.adapters.workbook import create_workbook_to_cloud

    payload = create_workbook_to_cloud(
        {
            "workbookId": "abc123abc123a",
            "collectionId": None,
            "title": "T",
            "description": None,
            "tenantId": "common",
            "meta": {},
            "createdBy": "admin",
            "createdAt": "2026-01-01T00:00:00.000Z",
            "updatedBy": "admin",
            "updatedAt": "2026-01-01T00:00:00.000Z",
            "status": "active",
        }
    )
    validate_schema("CreateWorkbookResult", payload)


def test_create_connection_result_matches_cloud_schema():
    validate_schema("CreateConnectionResult", {"id": "x"})


OSS_GET_CONNECTION = {
    "port": 8443,
    "data_export_forbidden": "off",
    "description": "",
    "db_name": None,
    "id": "1vjdwa9c1h34k",
    "cache_ttl_sec": None,
    "name": "recon-ch",
    "raw_sql_level": "off",
    "readonly": 2,
    "secure": "on",
    "meta": {},
    "workbook_id": "82qk3h9qimeqr",
    "updated_at": "2026-08-14T15:22:28.193Z",
    "key": "2281424117355774992/recon-ch",
    "host": "ch.invalid.example",
    "created_at": "2026-08-14T15:22:28.193Z",
    "username": "default",
    "db_type": "clickhouse",
    "options": {
        "allow_dataset_usage": True,
        "allow_dashsql_usage": False,
    },
}


def test_adapted_get_connection_matches_cloud_schema():
    from app.adapters.connection import connection_to_cloud

    payload = connection_to_cloud(OSS_GET_CONNECTION)
    validate_schema("ConnectionRead", payload)


def test_mapped_workbooks_list_matches_cloud_schema():
    validate_schema(
        "GetWorkbooksListResult",
        {
            "workbooks": [
                {
                    "workbookId": "abc123abc123a",
                    "collectionId": None,
                    "title": "Demo",
                    "description": None,
                    "tenantId": "common",
                    "meta": {},
                    "createdBy": "admin",
                    "createdAt": "2026-01-01T00:00:00.000Z",
                    "updatedBy": "admin",
                    "updatedAt": "2026-01-01T00:00:00.000Z",
                    "status": "active",
                }
            ]
        },
    )


OSS_GET_DASHBOARD = {
    "entryId": "ythj3vhvwphmh",
    "scope": "dash",
    "type": "dash",
    "key": "pk8aul3ruj188/demo-dash",
    "createdBy": "uid:systemId",
    "createdAt": "2026-08-14T16:14:25.036Z",
    "updatedBy": "uid:systemId",
    "updatedAt": "2026-08-14T16:14:25.036Z",
    "savedId": "zuik4wiwxqioi",
    "publishedId": None,
    "revId": "zuik4wiwxqioi",
    "tenantId": "common",
    "data": {
        "salt": "test-salt",
        "tabs": [
            {
                "id": "t1",
                "items": [],
                "title": "Tab",
                "layout": [],
                "aliases": {},
            }
        ],
        "counter": 1,
        "settings": {},
        "schemeVersion": 8,
    },
    "meta": {},
    "annotation": None,
    "version": None,
    "hidden": False,
    "public": False,
    "workbookId": "pk8aul3ruj188",
    "collectionId": None,
}


def test_adapted_get_dashboard_matches_cloud_schema():
    from app.adapters.dashboard import dashboard_result

    payload = dashboard_result(OSS_GET_DASHBOARD)
    validate_schema("GetDashboardV1Result", payload)
    validate_schema("DashboardV1", payload["entry"])
