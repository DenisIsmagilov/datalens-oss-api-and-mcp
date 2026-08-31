from typing import Any, get_args

from app.errors import ApiError
from app.models.generated import ConnectionRead

_OSS_EXTRAS = ("db_type", "options", "workbook_id")


def _variant_model(conn_type: Any):
    if not isinstance(conn_type, str) or not conn_type:
        return None
    annotation = ConnectionRead.model_fields["root"].annotation
    for variant in get_args(annotation):
        type_field = getattr(variant, "model_fields", {}).get("type")
        if type_field is None:
            continue
        allowed = get_args(type_field.annotation)
        default = getattr(type_field, "default", None)
        if conn_type in allowed or default == conn_type:
            return variant
    return None


def _fill_required_strings(item: dict, variant: Any) -> dict:
    if variant is None:
        return item
    for name, field in variant.model_fields.items():
        if name in item or not field.is_required():
            continue
        if field.annotation is str:
            item[name] = ""
    return item


def connection_to_cloud(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    item = dict(raw)
    item.pop("password", None)
    if not item.get("type") and item.get("db_type"):
        item["type"] = item["db_type"]
    for key in _OSS_EXTRAS:
        item.pop(key, None)
    variant = _variant_model(item.get("type"))
    if variant is not None:
        allowed = set(variant.model_fields)
        item = {key: value for key, value in item.items() if key in allowed}
    return _fill_required_strings(item, variant)


def create_connection_to_cloud(raw: Any) -> dict:
    if not isinstance(raw, dict) or "id" not in raw or raw["id"] in (None, ""):
        raise ApiError(
            500,
            "INTERNAL",
            "control-api createConnection response is missing id",
        )
    return {"id": raw["id"]}


def empty_to_cloud(raw: Any) -> dict:
    if raw is None:
        return {}
    return {}
