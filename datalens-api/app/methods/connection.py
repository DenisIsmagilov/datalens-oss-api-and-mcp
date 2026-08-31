from app.adapters.connection import (
    connection_to_cloud,
    create_connection_to_cloud,
    empty_to_cloud,
)
from app.auth import AuthContext
from app.clients.control_api import get_control_api_client
from app.models.generated import ConnectionCreate, ConnectionRead, CreateConnectionResult
from app.models.rpc_bi import (
    DeleteConnectionArgs,
    EmptyResult,
    GetConnectionArgs,
    UpdateConnectionArgs,
)


def _dump_create(args: ConnectionCreate) -> dict:
    payload = args.model_dump(by_alias=True, exclude_unset=True, mode="json")
    if isinstance(payload, dict) and set(payload.keys()) == {"root"}:
        inner = payload["root"]
        if isinstance(inner, dict):
            return inner
    return payload


async def create_connection(
    args: ConnectionCreate, _ctx: AuthContext
) -> CreateConnectionResult:
    client = await get_control_api_client()
    raw = await client.request(
        "POST",
        "/api/v1/connections/",
        json=_dump_create(args),
    )
    return CreateConnectionResult.model_validate(create_connection_to_cloud(raw))


async def get_connection(args: GetConnectionArgs, _ctx: AuthContext) -> ConnectionRead:
    payload = args.model_dump(by_alias=True, exclude_none=True)
    connection_id = payload.pop("connectionId")
    params = {}
    if "rev_id" in payload:
        params["rev_id"] = payload["rev_id"]
    headers = {}
    if payload.get("bindedDatasetId"):
        headers["x-dl-dataset-id"] = payload["bindedDatasetId"]
    client = await get_control_api_client()
    raw = await client.request(
        "GET",
        f"/api/v1/connections/{connection_id}",
        params=params or None,
        headers=headers or None,
    )
    return ConnectionRead.model_validate(connection_to_cloud(raw))


async def update_connection(
    args: UpdateConnectionArgs, _ctx: AuthContext
) -> EmptyResult:
    client = await get_control_api_client()
    raw = await client.request(
        "PUT",
        f"/api/v1/connections/{args.connectionId}",
        json=args.data,
    )
    return EmptyResult.model_validate(empty_to_cloud(raw))


async def delete_connection(
    args: DeleteConnectionArgs, _ctx: AuthContext
) -> EmptyResult:
    client = await get_control_api_client()
    raw = await client.request(
        "DELETE",
        f"/api/v1/connections/{args.connectionId}",
    )
    return EmptyResult.model_validate(empty_to_cloud(raw))
