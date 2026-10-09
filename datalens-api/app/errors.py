from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


_US_STATUS_TO_CODE = {
    400: ("INVALID_ARGUMENT", 400),
    401: ("UNAUTHENTICATED", 401),
    403: ("PERMISSION_DENIED", 403),
    404: ("NOT_FOUND", 404),
    409: ("ALREADY_EXISTS", 409),
    423: ("FAILED_PRECONDITION", 409),
}


def raise_from_us(status_code: int, body: dict | str) -> None:
    if isinstance(body, dict):
        message = str(
            body.get("message")
            or body.get("error")
            or body.get("code")
            or body
        )
    else:
        message = str(body)
    if status_code >= 500:
        raise ApiError(500, "INTERNAL", message)
    code, http = _US_STATUS_TO_CODE.get(status_code, ("INVALID_ARGUMENT", status_code))
    raise ApiError(http, code, message, details=body if isinstance(body, dict) else {})


def _cloud_error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "details": details or {},
    }


def internal_error_response(_exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_cloud_error_body("INTERNAL", "Internal error"),
    )


def _public_validation_errors(exc: RequestValidationError) -> list[dict]:
    # ctx может содержать объект исключения (не сериализуется), input — значения фильтров
    return [
        {key: value for key, value in error.items() if key not in ("ctx", "input", "url")}
        for error in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_cloud_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_cloud_error_body(
                "INVALID_ARGUMENT",
                "Invalid request",
                {"errors": _public_validation_errors(exc)},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        return internal_error_response(exc)
