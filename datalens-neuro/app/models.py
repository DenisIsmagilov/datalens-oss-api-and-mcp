from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    status: str
    duration_ms: int
    row_count: int | None = None


@dataclass
class TurnResult:
    reply: str
    stop_reason: str
    steps: list[Step] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    rounds: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
