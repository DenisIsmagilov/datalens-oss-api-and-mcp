#!/usr/bin/env python3
"""Prepare the cloud OpenAPI spec for datamodel-codegen.

Flattens dashboard selector sources so widget fields survive codegen, and
adds ``asGroup`` to the control group impact enum. If codegen cannot handle
OpenAPI 3.1 nullable unions (`type: ["string", "null"]`), pass
``--normalize-31`` to rewrite them as OpenAPI 3.0 (`type: string`,
`nullable: true`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _is_null_type_union(value: Any) -> bool:
    return (
        isinstance(value, list)
        and "null" in value
        and any(item != "null" and isinstance(item, str) for item in value)
    )


def normalize_openapi_31_nullables(node: Any) -> Any:
    """Convert OpenAPI 3.1 type unions with null into 3.0 nullable fields."""
    if isinstance(node, dict):
        converted = {key: normalize_openapi_31_nullables(value) for key, value in node.items()}
        type_value = converted.get("type")
        if _is_null_type_union(type_value):
            non_null = [item for item in type_value if item != "null"]
            if len(non_null) == 1:
                converted["type"] = non_null[0]
            else:
                converted["type"] = non_null
            converted["nullable"] = True
        return converted
    if isinstance(node, list):
        return [normalize_openapi_31_nullables(item) for item in node]
    return node


_SOURCE_SCHEMAS = ("DashControlSourceDataset", "DashControlSourceManual")
_SOURCE_IDENTITY = {
    "datasetId",
    "datasetFieldId",
    "datasetFieldType",
    "fieldName",
    "acceptableValues",
}


def _deref(schemas: dict[str, Any], node: Any) -> Any:
    seen: set[str] = set()
    while isinstance(node, dict) and "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            break
        seen.add(name)
        node = schemas[name]
    return node


def _collect_properties(schemas: dict[str, Any], node: Any) -> dict[str, Any]:
    node = _deref(schemas, node)
    if not isinstance(node, dict):
        return {}
    if "allOf" in node:
        merged: dict[str, Any] = {}
        for part in node["allOf"]:
            merged.update(_collect_properties(schemas, part))
        return merged
    if "oneOf" in node:
        merged = {}
        for part in node["oneOf"]:
            for key, value in _collect_properties(schemas, part).items():
                merged.setdefault(key, value)
        return merged
    return dict(node.get("properties") or {})


def _collect_required(schemas: dict[str, Any], node: Any) -> list[str]:
    node = _deref(schemas, node)
    if not isinstance(node, dict):
        return []
    if "allOf" in node:
        required: list[str] = []
        for part in node["allOf"]:
            required.extend(_collect_required(schemas, part))
        return required
    if "oneOf" in node:
        return []
    return [item for item in node.get("required") or [] if isinstance(item, str)]


def _loose_widget_property(value: Any) -> dict[str, Any]:
    description = value.get("description") if isinstance(value, dict) else None
    if description:
        return {"description": description}
    return {}


def patch_dashboard_control_roundtrip(spec: dict[str, Any]) -> dict[str, Any]:
    """Keep OSS selector fields that datamodel-codegen drops from allOf.

    Cloud ``DashControlSource*`` schemas compose ``DashControlElement`` via
    allOf. The generator keeps only dataset/manual identifiers, so a later
    ``updateDashboard`` writes United Storage without ``elementType``. Widget
    fields stay unconstrained: an enum would reject a value OSS already stored.
    ``additionalProperties`` keeps keys the cloud list does not name.
    External sources stay chart-only. Group ``impactType`` gains ``asGroup``.
    """
    schemas = spec["components"]["schemas"]
    for name in _SOURCE_SCHEMAS:
        original = schemas[name]
        properties = _collect_properties(schemas, original)
        required: list[str] = []
        for item in _collect_required(schemas, original):
            if item in _SOURCE_IDENTITY and item not in required:
                required.append(item)
        loose: dict[str, Any] = {}
        for key, value in properties.items():
            if key in _SOURCE_IDENTITY:
                loose[key] = value
            elif key == "elementType":
                loose[key] = {"description": "Control element type."}
            else:
                loose[key] = _loose_widget_property(value)
        flattened: dict[str, Any] = {
            "type": "object",
            "additionalProperties": True,
            "properties": loose,
            "required": required,
        }
        if isinstance(original, dict) and original.get("description"):
            flattened["description"] = original["description"]
        schemas[name] = flattened
    impact = schemas["DashGroupControl"]["properties"]["impactType"]
    enum = impact.get("enum")
    if isinstance(enum, list) and "asGroup" not in enum:
        enum.append("asGroup")
    return spec


def prepare(input_path: Path, output_path: Path, *, normalize: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    spec = json.loads(input_path.read_text(encoding="utf-8"))
    if normalize:
        spec = normalize_openapi_31_nullables(spec)
        if isinstance(spec, dict) and str(spec.get("openapi", "")).startswith("3.1"):
            spec["openapi"] = "3.0.3"
    patch_dashboard_control_roundtrip(spec)
    output_path.write_text(
        json.dumps(spec, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--normalize-31",
        action="store_true",
        help="Normalize OpenAPI 3.1 nullables to 3.0 before writing.",
    )
    args = parser.parse_args()
    prepare(args.input, args.output, normalize=args.normalize_31)


if __name__ == "__main__":
    main()
