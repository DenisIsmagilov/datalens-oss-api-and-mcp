import json
import re

import pytest
from jsonschema import Draft202012Validator

from app.tools import build_registry
from app.tools.base import ToolRegistry

EXPECTED = [
    "list_workbook_entries",
    "get_dashboard",
    "get_chart",
    "get_dataset",
    "query_dataset",
    "get_dataset_field_values",
    "get_chart_data",
    "semantic_search",
    "get_intent",
]


def test_tool_schemas_are_valid_and_inlined():
    schemas = build_registry().schemas()
    assert [s["function"]["name"] for s in schemas] == EXPECTED
    for schema in schemas:
        function = schema["function"]
        assert schema["type"] == "function"
        assert re.fullmatch(r"[a-z_]{3,64}", function["name"])
        assert len(function["description"]) >= 40
        parameters = function["parameters"]
        assert parameters["type"] == "object"
        Draft202012Validator.check_schema(parameters)
        assert "$ref" not in json.dumps(parameters) and "$defs" not in parameters


def test_property_named_title_survives_inlining():
    parameters = build_registry().get("query_dataset").schema()["function"]["parameters"]
    calculated = parameters["properties"]["calculatedFields"]["items"]
    assert set(calculated["properties"]) == {"title", "formula"}
    assert calculated["required"] == ["title", "formula"]


def test_duplicate_names_rejected():
    tool = build_registry().get("get_dataset")
    with pytest.raises(ValueError):
        ToolRegistry([tool, tool])
