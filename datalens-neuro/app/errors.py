from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_HTTP_CODES = {401: "UNAUTHENTICATED", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


class NeuroError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"code": code, "message": message, "details": details or {}}


def internal_error_response() -> JSONResponse:
    return JSONResponse(status_code=500, content=error_body("INTERNAL", "Internal error"))


def http_error_code(status_code: int) -> str:
    if status_code in _HTTP_CODES:
        return _HTTP_CODES[status_code]
    return "INTERNAL" if status_code >= 500 else "INVALID_ARGUMENT"


def public_validation_errors(errors: list[dict]) -> list[dict]:
    # ctx может содержать объект исключения, input — значения пользователя
    return [
        {key: value for key, value in error.items() if key not in ("ctx", "input", "url")}
        for error in errors
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NeuroError)
    async def _neuro_error(_request: Request, exc: NeuroError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(http_error_code(exc.status_code), str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_body(
                "INVALID_ARGUMENT",
                "Invalid request",
                {"errors": public_validation_errors(exc.errors())},
            ),
        )
