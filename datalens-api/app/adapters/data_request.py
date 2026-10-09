import re
from dataclasses import dataclass

from app.errors import ApiError
from app.models.rpc_data import CalculatedField, DataFilter, OrderBy

_DB_CALL = re.compile(r"\bDB_CALL_\w*", re.IGNORECASE)
_MAX_AVAILABLE_FIELDS = 50
CALC_GUID_PREFIX = "__calc_"
RANGE_MIN_GUID = "__range_min"
RANGE_MAX_GUID = "__range_max"


@dataclass(frozen=True)
class DatasetField:
    guid: str
    title: str
    data_type: str


def fields_from_schema(body: dict) -> list[DatasetField]:
    return [
        DatasetField(
            guid=str(item["guid"]),
            title=str(item.get("title") or item["guid"]),
            data_type=str(item.get("data_type") or ""),
        )
        for item in body.get("fields", [])
        if isinstance(item, dict) and item.get("guid")
    ]


def resolve_field(ref: str, fields: list[DatasetField]) -> DatasetField:
    for field in fields:
        if field.guid == ref:
            return field
    matches = [field for field in fields if field.title == ref]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ApiError(
            400,
            "INVALID_ARGUMENT",
            f"Ambiguous field: {ref}",
            details={
                "field": ref,
                "candidates": [{"title": f.title, "guid": f.guid} for f in matches],
            },
        )
    raise ApiError(
        400,
        "INVALID_ARGUMENT",
        f"Field not found: {ref}",
        details={
            "field": ref,
            "availableFields": [f.title for f in fields][:_MAX_AVAILABLE_FIELDS],
        },
    )


def _ref(field: DatasetField) -> dict:
    return {"type": "id", "id": field.guid}


def _filter_value(value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _calculated_fields(
    items: list[CalculatedField], dataset_fields: list[DatasetField]
) -> list[DatasetField]:
    taken = {field.title for field in dataset_fields}
    result: list[DatasetField] = []
    for index, item in enumerate(items):
        if _DB_CALL.search(item.formula):
            raise ApiError(
                400,
                "INVALID_ARGUMENT",
                "DB_CALL_* functions are not allowed",
                details={"formulaTitle": item.title},
            )
        if item.title in taken:
            raise ApiError(
                400,
                "INVALID_ARGUMENT",
                f"Calculated field title is already used: {item.title}",
                details={"formulaTitle": item.title},
            )
        taken.add(item.title)
        result.append(
            DatasetField(guid=f"{CALC_GUID_PREFIX}{index}", title=item.title, data_type="")
        )
    return result


def _formula_field(guid: str, title: str, formula: str) -> dict:
    return {
        "action": "add_field",
        "field": {"guid": guid, "title": title, "calc_mode": "formula", "formula": formula},
    }


def _filters(filters: list[DataFilter], fields: list[DatasetField]) -> list[dict]:
    return [
        {
            "ref": _ref(resolve_field(item.field, fields)),
            "operation": item.op.upper(),
            "values": [_filter_value(v) for v in item.values],
        }
        for item in filters
    ]


def build_result_body(
    *,
    fields: list[str],
    calculated: list[CalculatedField],
    filters: list[DataFilter],
    order_by: list[OrderBy],
    dataset_fields: list[DatasetField],
    limit: int,
) -> dict:
    calc = _calculated_fields(calculated, dataset_fields)
    known = dataset_fields + calc
    body: dict = {
        "fields": [{"ref": _ref(resolve_field(ref, known))} for ref in fields],
        "limit": limit + 1,
    }
    if calc:
        body["updates"] = [
            _formula_field(c.guid, c.title, item.formula) for item, c in zip(calculated, calc)
        ]
    if filters:
        body["filters"] = _filters(filters, known)
    if order_by:
        body["order_by"] = [
            {"ref": _ref(resolve_field(item.field, known)), "direction": item.direction}
            for item in order_by
        ]
    return body


def build_distinct_body(
    *,
    field: str,
    search: str | None,
    filters: list[DataFilter],
    dataset_fields: list[DatasetField],
    limit: int,
) -> tuple[dict, DatasetField]:
    target = resolve_field(field, dataset_fields)
    body_filters = _filters(filters, dataset_fields)
    if search:
        body_filters.append({"ref": _ref(target), "operation": "ICONTAINS", "values": [search]})
    body: dict = {
        "fields": [{"ref": _ref(target), "role_spec": {"role": "distinct"}}],
        "limit": limit + 1,
    }
    if body_filters:
        body["filters"] = body_filters
    return body, target


def _formula_ref(title: str) -> str:
    return "[" + title.replace("\\", "\\\\").replace("]", "\\]") + "]"


def build_range_body(
    *,
    field: str,
    filters: list[DataFilter],
    dataset_fields: list[DatasetField],
) -> tuple[dict, DatasetField]:
    target = resolve_field(field, dataset_fields)
    ref = _formula_ref(target.title)
    body: dict = {
        "fields": [
            {"ref": {"type": "id", "id": RANGE_MIN_GUID}},
            {"ref": {"type": "id", "id": RANGE_MAX_GUID}},
        ],
        "updates": [
            _formula_field(RANGE_MIN_GUID, RANGE_MIN_GUID, f"MIN({ref})"),
            _formula_field(RANGE_MAX_GUID, RANGE_MAX_GUID, f"MAX({ref})"),
        ],
        "limit": 1,
    }
    body_filters = _filters(filters, dataset_fields)
    if body_filters:
        body["filters"] = body_filters
    return body, target
