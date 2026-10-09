from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EntryId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]

FilterOp = Literal[
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "nin",
    "between",
    "contains",
    "icontains",
    "startswith",
    "isnull",
    "isnotnull",
]
Scalar = str | int | float | bool

_NO_VALUES = {"isnull", "isnotnull"}
_MANY_VALUES = {"in", "nin"}


class DataFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1)
    op: FilterOp
    values: list[Scalar] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def _check_values_count(self) -> "DataFilter":
        count = len(self.values)
        if self.op in _NO_VALUES:
            ok = count == 0
        elif self.op == "between":
            ok = count == 2
        elif self.op in _MANY_VALUES:
            ok = count >= 1
        else:
            ok = count == 1
        if not ok:
            raise ValueError(f"op {self.op!r} does not accept {count} values")
        return self


class CalculatedField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    formula: str = Field(min_length=1, max_length=5000)


class OrderBy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1)
    direction: Literal["asc", "desc"] = "asc"


class QueryDatasetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datasetId: EntryId
    fields: list[str] = Field(min_length=1, max_length=30)
    calculatedFields: list[CalculatedField] = Field(default_factory=list, max_length=10)
    filters: list[DataFilter] = Field(default_factory=list, max_length=20)
    orderBy: list[OrderBy] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=100, ge=1)


class Column(BaseModel):
    title: str
    dataType: str


class QueryDatasetResult(BaseModel):
    columns: list[Column]
    rows: list[list[Any]]
    rowCount: int
    truncated: bool


class GetDatasetFieldValuesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datasetId: EntryId
    field: str = Field(min_length=1)
    mode: Literal["distinct", "range"] = "distinct"
    search: str | None = Field(default=None, max_length=200)
    filters: list[DataFilter] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=100, ge=1)


class GetDatasetFieldValuesResult(BaseModel):
    field: str
    values: list[Any] | None = None
    truncated: bool | None = None
    min: Any = None
    max: Any = None


class GetChartDataArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chartId: EntryId
    params: dict[str, str | list[str]] = Field(default_factory=dict)


class GetChartDataResult(BaseModel):
    chartId: str
    title: str
    visualization: str
    datasetIds: list[str]
    columns: list[Column]
    rows: list[list[Any]]
    rowCount: int
    truncated: bool
    normalized: bool
    note: str | None = None
