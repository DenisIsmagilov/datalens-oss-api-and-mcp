from pydantic import ValidationError

from app.adapters.connection import empty_to_cloud
from app.adapters.dataset import dataset_to_cloud
from app.auth import AuthContext
from app.clients.control_api import get_control_api_client
from app.errors import ApiError
from app.models.generated import DatasetCreate, DatasetRead
from app.models.rpc_bi import (
    DeleteDatasetArgs,
    EmptyResult,
    GetDatasetArgs,
    UpdateDatasetArgs,
    ValidateDatasetArgs,
)


def _dump_create(args: DatasetCreate) -> dict:
    payload = args.model_dump(by_alias=True, exclude_unset=True, mode="json")
    if isinstance(payload, dict) and set(payload.keys()) == {"root"}:
        inner = payload["root"]
        if isinstance(inner, dict):
            return inner
    return payload


def _as_dataset_read(raw: dict, *, dataset_id: str | None = None) -> DatasetRead:
    adapted = dataset_to_cloud(raw)
    if dataset_id and not adapted.get("id"):
        adapted["id"] = dataset_id
    return DatasetRead.model_validate(adapted)


def _workbook_params(*sources: dict) -> dict:
    params: dict = {}
    for source in sources:
        if source.get("rev_id") is not None:
            params["rev_id"] = source["rev_id"]
        workbook_id = source.get("workbookId")
        if workbook_id:
            params["workbook_id"] = workbook_id
    return params


def _dataset_id_headers(*, dataset_id: str | None, binded_dataset_id: str | None) -> dict:
    header_value = binded_dataset_id or dataset_id
    if not header_value:
        return {}
    return {"x-dl-dataset-id": header_value}


async def create_dataset(args: DatasetCreate, _ctx: AuthContext) -> DatasetRead:
    client = await get_control_api_client()
    raw = await client.request(
        "POST",
        "/api/v1/datasets/",
        json=_dump_create(args),
    )
    return _as_dataset_read(raw)


async def get_dataset(args: GetDatasetArgs, _ctx: AuthContext) -> DatasetRead:
    payload = args.model_dump(by_alias=True, exclude_none=True)
    dataset_id = payload.pop("datasetId")
    params = _workbook_params(payload)
    client = await get_control_api_client()
    raw = await client.request(
        "GET",
        f"/api/v1/datasets/{dataset_id}/versions/draft",
        params=params or None,
    )
    return _as_dataset_read(raw, dataset_id=dataset_id)


async def update_dataset(
    args: UpdateDatasetArgs, _ctx: AuthContext
) -> DatasetRead:
    params = _workbook_params({"workbookId": args.workbookId})
    client = await get_control_api_client()
    raw = await client.request(
        "PUT",
        f"/api/v1/datasets/{args.datasetId}/versions/draft",
        json=args.data,
        params=params or None,
    )
    return _as_dataset_read(raw, dataset_id=args.datasetId)


async def delete_dataset(
    args: DeleteDatasetArgs, _ctx: AuthContext
) -> EmptyResult:
    client = await get_control_api_client()
    raw = await client.request(
        "DELETE",
        f"/api/v1/datasets/{args.datasetId}",
    )
    return EmptyResult.model_validate(empty_to_cloud(raw))


def _validate_body(data: dict | None) -> dict:
    if not data:
        return {}
    if "dataset" in data or "updates" in data:
        body: dict = {}
        if "dataset" in data:
            body["dataset"] = data["dataset"]
        if "updates" in data:
            body["updates"] = data["updates"]
        return body
    return data


def _nonempty_dataset(details: dict) -> bool:
    dataset = details.get("dataset")
    return isinstance(dataset, dict) and bool(dataset)


async def validate_dataset(
    args: ValidateDatasetArgs, _ctx: AuthContext
) -> DatasetRead:
    client = await get_control_api_client()
    params = _workbook_params({"workbookId": args.workbookId})
    headers = _dataset_id_headers(
        dataset_id=args.datasetId,
        binded_dataset_id=args.bindedDatasetId,
    )
    try:
        raw = await client.request(
            "POST",
            f"/api/v1/datasets/{args.datasetId}/versions/draft/validators/schema",
            json=_validate_body(args.data),
            params=params or None,
            headers=headers or None,
        )
    except ApiError as exc:
        if exc.status_code == 400 and isinstance(exc.details, dict) and _nonempty_dataset(
            exc.details
        ):
            try:
                return _as_dataset_read(exc.details, dataset_id=args.datasetId)
            except ValidationError as validation_exc:
                raise ApiError(
                    400,
                    "INVALID_ARGUMENT",
                    "validateDataset 400 body is not DatasetRead",
                    details={"errors": validation_exc.errors()},
                ) from validation_exc
        raise
    return _as_dataset_read(raw, dataset_id=args.datasetId)
