import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatContext(_In):
    dashboardId: str | None = Field(None, max_length=64)
    chartId: str | None = Field(None, max_length=64)
    tabId: str | None = Field(None, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def _small_params(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False, default=str)) > 2000:
            raise ValueError("params are too large (max 2000 characters of JSON)")
        return value


class ChatUser(_In):
    externalId: str = Field(min_length=1, max_length=200)
    name: str | None = Field(None, max_length=200)


class ChatRequest(_In):
    conversationId: str | None = Field(None, pattern=r"^c_[0-9a-f]{20}$")
    message: str = Field(min_length=1, max_length=4000)
    pack: str | None = Field(None, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    context: ChatContext | None = None
    user: ChatUser | None = None


class StepOut(BaseModel):
    tool: str
    args: dict[str, Any]
    status: str
    durationMs: int
    rowCount: int | None = None


class SourceOut(BaseModel):
    type: str
    id: str


class UsageOut(BaseModel):
    rounds: int
    promptTokens: int
    completionTokens: int


class ChatResponse(BaseModel):
    conversationId: str
    reply: str
    stopReason: str
    steps: list[StepOut]
    sources: list[SourceOut]
    usage: UsageOut
