import json
from dataclasses import dataclass
from urllib.parse import unquote

import jwt

from app.errors import NeuroError


@dataclass(frozen=True)
class UiUser:
    user_id: str
    roles: tuple[str, ...]


def access_token_from_cookie(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name != "auth" or not value:
            continue
        try:
            payload = json.loads(unquote(value))
        except ValueError:
            return None
        token = payload.get("accessToken") if isinstance(payload, dict) else None
        return token if isinstance(token, str) and token else None
    return None


# datalens-auth подписывает accessToken алгоритмом PS256. RS256 оставлен:
# тот же RSA-ключ его тоже проверяет, юнит-тесты выпускают RS256.
_ALLOWED_ALGS = ["PS256", "RS256"]


def verify_access_token(token: str, public_key_pem: str) -> UiUser:
    if not public_key_pem.strip():
        raise NeuroError(401, "UNAUTHENTICATED", "UI auth is not configured")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in _ALLOWED_ALGS:
            raise NeuroError(401, "UNAUTHENTICATED", "Unsupported token algorithm")
        claims = jwt.decode(token, public_key_pem, algorithms=_ALLOWED_ALGS)
    except NeuroError:
        raise
    except jwt.PyJWTError:
        raise NeuroError(401, "UNAUTHENTICATED", "Missing or invalid token") from None
    user_id = claims.get("userId")
    roles = claims.get("roles")
    if not isinstance(user_id, str) or not user_id or not isinstance(roles, list):
        raise NeuroError(401, "UNAUTHENTICATED", "Missing or invalid token")
    return UiUser(user_id, tuple(role for role in roles if isinstance(role, str)))
