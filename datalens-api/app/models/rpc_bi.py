from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GetConnectionArgs(BaseModel):
    connectionId: str
    workbookId: str | None = None
    bindedDatasetId: str | None = None
    rev_id: str | None = None


class UpdateConnectionArgs(BaseModel):
    model_config = ConfigDict(extra="allow")
    connectionId: str
    data: dict


class DeleteConnectionArgs(BaseModel):
    connectionId: str


class GetDatasetArgs(BaseModel):
    datasetId: str
    workbookId: str | None = None
    rev_id: str | None = None


class UpdateDatasetArgs(BaseModel):
    model_config = ConfigDict(extra="allow")
    datasetId: str
    data: dict
    workbookId: str | None = None


class DeleteDatasetArgs(BaseModel):
    datasetId: str


class ValidateDatasetArgs(BaseModel):
    model_config = ConfigDict(extra="allow")
    datasetId: str
    workbookId: str | None = None
    bindedDatasetId: str | None = None
    data: dict | None = None


class ValidateDatasetFormulaArgs(BaseModel):
    datasetId: str
    formula: str = Field(min_length=1, max_length=5000)


class ValidateDatasetFormulaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid: Literal[True] = True


class EmptyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChartResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    entryId: str
