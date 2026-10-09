from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.clients.datalens_api import DatalensApiClient, DatalensApiError
from app.packs import Pack
from app.tools.scope_cache import ScopeCache


class ToolError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class ToolContext:
    api: DatalensApiClient
    pack: Pack
    scope: ScopeCache


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_inline(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _inline(defs[node["$ref"].rsplit("/", 1)[-1]], defs)
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "title":
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: _inline(sub, defs) for name, sub in value.items()}
        else:
            out[key] = _inline(value, defs)
    return out


def openai_parameters(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    return _inline(schema, defs)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], Awaitable[dict]]
    source_type: str | None = None
    source_arg: str | None = None

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": openai_parameters(self.args_model),
            },
        }


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        names = [tool.name for tool in tools]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate tool names: {duplicates}")
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]


async def run_tool(tool: Tool, raw_args: dict[str, Any], ctx: ToolContext) -> dict:
    try:
        args = tool.args_model.model_validate(raw_args)
    except ValidationError as exc:
        raise ToolError(
            "INVALID_ARGUMENT",
            "Arguments do not match the tool schema",
            {"errors": [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]},
        ) from exc
    try:
        return await tool.handler(args, ctx)
    except DatalensApiError as exc:
        raise ToolError(exc.code, exc.message, exc.details) from exc
