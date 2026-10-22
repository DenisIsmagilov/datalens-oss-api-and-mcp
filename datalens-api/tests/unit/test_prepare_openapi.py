import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "prepare_openapi.py"
_CLOUD = (
    Path(__file__).resolve().parents[3]
    / "docs/superpowers/reference/datalens-cloud-openapi.json"
)


def _prepare_module():
    spec = importlib.util.spec_from_file_location("prepare_openapi", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _element_branch(element_type: str, extra: dict | None = None) -> dict:
    properties = {
        "elementType": {
            "type": "string",
            "enum": [element_type],
            "description": f"{element_type} control type.",
        },
        "showTitle": {
            "type": "boolean",
            "description": "Whether to show the control title.",
        },
        "defaultValue": {"type": "string", "description": "Default value."},
    }
    if extra:
        properties.update(extra)
    return {
        "type": "object",
        "properties": properties,
        "required": ["elementType"],
    }


def _spec() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "paths": {},
        "components": {
            "schemas": {
                "DashControlElement": {
                    "oneOf": [
                        _element_branch("select"),
                        _element_branch(
                            "date",
                            {
                                "isRange": {
                                    "type": "boolean",
                                    "description": "Whether the control selects a date range.",
                                }
                            },
                        ),
                    ]
                },
                "DashControlSourceDataset": {
                    "allOf": [
                        {"$ref": "#/components/schemas/DashControlElement"},
                        {
                            "type": "object",
                            "properties": {
                                "datasetId": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "Source dataset identifier.",
                                }
                            },
                            "required": ["datasetId"],
                        },
                    ],
                    "description": "Dataset control source.",
                },
                "DashControlSourceManual": {
                    "allOf": [
                        {"$ref": "#/components/schemas/DashControlElement"},
                        {
                            "type": "object",
                            "properties": {
                                "fieldName": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "Parameter name for the manual control.",
                                }
                            },
                            "required": ["fieldName"],
                        },
                    ],
                    "description": "Manual control source.",
                },
                "DashControlSourceExternal": {
                    "type": "object",
                    "properties": {
                        "chartId": {"type": "string", "minLength": 1},
                    },
                    "required": ["chartId"],
                    "description": "External control source.",
                },
                "DashGroupControl": {
                    "type": "object",
                    "properties": {
                        "impactType": {
                            "type": "string",
                            "enum": ["allTabs", "currentTab", "selectedTabs"],
                            "description": "Tabs affected by the control group.",
                        }
                    },
                },
            }
        },
    }


def test_prepare_flattens_selector_source_and_keeps_group_as_group(tmp_path: Path):
    module = _prepare_module()
    source = tmp_path / "in.json"
    target = tmp_path / "out.json"
    source.write_text(json.dumps(_spec()), encoding="utf-8")
    module.prepare(source, target, normalize=False)
    spec = json.loads(target.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    dataset = schemas["DashControlSourceDataset"]
    manual = schemas["DashControlSourceManual"]
    assert "allOf" not in dataset
    assert "allOf" not in manual
    assert dataset["additionalProperties"] is True
    assert manual["additionalProperties"] is True
    assert dataset["required"] == ["datasetId"]
    assert manual["required"] == ["fieldName"]
    assert set(dataset["properties"]) >= {
        "datasetId",
        "elementType",
        "showTitle",
        "defaultValue",
    }
    assert "isRange" in manual["properties"]
    assert "enum" not in dataset["properties"]["elementType"]
    assert "type" not in dataset["properties"]["elementType"]
    assert dataset["properties"]["datasetId"]["minLength"] == 1

    external = schemas["DashControlSourceExternal"]
    assert external["properties"].keys() == {"chartId"}
    assert "additionalProperties" not in external

    assert "asGroup" in schemas["DashGroupControl"]["properties"]["impactType"]["enum"]


@pytest.mark.skipif(not _CLOUD.is_file(), reason="cloud OpenAPI reference is not in this tree")
def test_prepare_patches_cloud_reference(tmp_path: Path):
    module = _prepare_module()
    target = tmp_path / "prepared.json"
    module.prepare(_CLOUD, target, normalize=False)
    schemas = json.loads(target.read_text(encoding="utf-8"))["components"]["schemas"]
    dataset = schemas["DashControlSourceDataset"]
    assert dataset["additionalProperties"] is True
    assert "elementType" in dataset["properties"]
    assert "asGroup" in schemas["DashGroupControl"]["properties"]["impactType"]["enum"]
    assert "additionalProperties" not in schemas["DashControlSourceExternal"]
