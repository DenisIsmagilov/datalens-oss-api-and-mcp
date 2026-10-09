import re
import uuid
from contextvars import ContextVar, Token

_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_request_id(raw: str | None) -> str:
    if raw and _SAFE_REQUEST_ID.fullmatch(raw):
        return raw
    return new_request_id()


def set_request_id(value: str) -> Token:
    return _REQUEST_ID.set(value)


def reset_request_id(token: Token) -> None:
    _REQUEST_ID.reset(token)


def current_request_id() -> str:
    return _REQUEST_ID.get() or new_request_id()
