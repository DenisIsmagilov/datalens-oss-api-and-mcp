#!/usr/bin/env python3
"""Prepare the cloud OpenAPI spec for datamodel-codegen.

Copies the reference as-is. If codegen cannot handle OpenAPI 3.1
nullable unions (`type: ["string", "null"]`), normalize them to
OpenAPI 3.0 (`type: string`, `nullable: true`).
"""

from __future__ import annotations

import argparse
import json
import shutil
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


def prepare(input_path: Path, output_path: Path, *, normalize: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not normalize:
        shutil.copyfile(input_path, output_path)
        return
    spec = json.loads(input_path.read_text(encoding="utf-8"))
    prepared = normalize_openapi_31_nullables(spec)
    if isinstance(prepared, dict) and prepared.get("openapi", "").startswith("3.1"):
        prepared["openapi"] = "3.0.3"
    output_path.write_text(
        json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
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
