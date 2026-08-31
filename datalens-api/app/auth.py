from dataclasses import dataclass

from fastapi import Header, Request

from app.config import get_settings
from app.errors import ApiError

SUPPORTED_VERSIONS = {"2", "latest"}


@dataclass(frozen=True)
class AuthContext:
    token: str
    org_id: str | None
    api_version: str


def resolve_api_version(raw: str | None) -> str:
    settings = get_settings()
    value = (raw or settings.datalens_api_version_default or "2").strip()
    if value not in SUPPORTED_VERSIONS:
        raise ApiError(
            status_code=400,
            code="INVALID_ARGUMENT",
            message=f"Unsupported x-dl-api-version: {value}",
        )
    return "2"


def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dl_org_id: str | None = Header(default=None),
    x_dl_api_version: str | None = Header(default=None),
) -> AuthContext:
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHENTICATED", "Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.dl_api_token:
        raise ApiError(401, "UNAUTHENTICATED", "Invalid Bearer token")
    return AuthContext(
        token=token,
        org_id=x_dl_org_id,
        api_version=resolve_api_version(x_dl_api_version),
    )
