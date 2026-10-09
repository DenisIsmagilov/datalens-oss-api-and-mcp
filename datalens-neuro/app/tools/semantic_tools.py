from pydantic import BaseModel, ConfigDict, Field

from app import semantic
from app.tools.base import Tool, ToolContext, ToolError


class SemanticSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)


class GetIntentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intentId: str = Field(min_length=1, max_length=100)


async def _search(args: SemanticSearchArgs, ctx: ToolContext) -> dict:
    return semantic.search(ctx.pack, args.query)


async def _get_intent(args: GetIntentArgs, ctx: ToolContext) -> dict:
    intent = semantic.get_intent(ctx.pack, args.intentId)
    if intent is None:
        raise ToolError(
            "NOT_FOUND",
            f"Unknown intent {args.intentId!r}",
            {"availableIntents": sorted((ctx.pack.glossary.get("intents") or {}).keys())},
        )
    return intent


SEMANTIC_TOOLS = [
    Tool(
        "semantic_search",
        "Search the domain glossary and catalog of this pack: business terms and synonyms, ready intents "
        "(which dataset and fields answer typical questions), datasets and fields by name, business rules. "
        "Call it first for questions in business terms.",
        SemanticSearchArgs,
        _search,
    ),
    Tool(
        "get_intent",
        "Full description of a ready intent from the pack glossary: dataset, date column, dimensions and "
        "measures (ClickHouse column names, usually equal to field guids), notes.",
        GetIntentArgs,
        _get_intent,
    ),
]
