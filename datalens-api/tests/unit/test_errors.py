import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import ApiError, raise_from_us, register_exception_handlers


def test_raise_from_us_404():
    with pytest.raises(ApiError) as exc:
        raise_from_us(404, {"message": "Workbook not found"})
    assert exc.value.status_code == 404
    assert exc.value.code == "NOT_FOUND"
    assert "Workbook not found" in exc.value.message


def test_raise_from_us_500():
    with pytest.raises(ApiError) as exc:
        raise_from_us(502, "bad gateway")
    assert exc.value.status_code == 500
    assert exc.value.code == "INTERNAL"


@pytest.mark.parametrize(
    ("us_status", "expected_code", "expected_http"),
    [
        (400, "INVALID_ARGUMENT", 400),
        (401, "UNAUTHENTICATED", 401),
        (403, "PERMISSION_DENIED", 403),
        (404, "NOT_FOUND", 404),
        (409, "ALREADY_EXISTS", 409),
        (423, "FAILED_PRECONDITION", 409),
        (422, "INVALID_ARGUMENT", 422),
        (418, "INVALID_ARGUMENT", 418),
    ],
)
def test_raise_from_us_status_mapping(us_status, expected_code, expected_http):
    with pytest.raises(ApiError) as exc:
        raise_from_us(us_status, {"message": "upstream error"})
    assert exc.value.status_code == expected_http
    assert exc.value.code == expected_code


def test_raise_from_us_preserves_dict_details():
    body = {"message": "conflict", "reason": "duplicate"}
    with pytest.raises(ApiError) as exc:
        raise_from_us(409, body)
    assert exc.value.details == body


def test_api_error_handler_response_format():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise ApiError(404, "NOT_FOUND", "missing", details={"id": "x"})

    response = TestClient(app).get("/boom")
    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "missing",
        "details": {"id": "x"},
    }


def test_request_validation_error_cloud_format():
    from app.main import create_app

    client = TestClient(create_app())
    response = client.post(
        "/rpc/getWorkbook",
        json={},
        headers={
            "Authorization": "Bearer test-dl-api-token",
            "x-dl-api-version": "2",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "INVALID_ARGUMENT"
    assert body["message"]
    assert "errors" in body["details"]


def test_unhandled_exception_cloud_format():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("unexpected secret detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL",
        "message": "Internal error",
        "details": {},
    }
