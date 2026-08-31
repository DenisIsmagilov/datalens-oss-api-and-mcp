from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth import AuthContext
from app.main import create_app
from app.registry import list_methods, register_rpc


class _PingArgs(BaseModel):
    pass


class _PingResult(BaseModel):
    pong: bool


async def _ping(_args: _PingArgs, _ctx: AuthContext) -> _PingResult:
    return _PingResult(pong=True)


def test_unknown_method_is_404():
    client = TestClient(create_app())
    response = client.post(
        "/rpc/definitelyMissing",
        json={},
        headers={"Authorization": "Bearer test-dl-api-token", "x-dl-api-version": "2"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_json_lists_only_registered_methods():
    app = FastAPI()
    register_rpc(app, "unitPing", _PingArgs, _PingResult, _ping)
    spec = app.openapi()
    assert "/rpc/unitPing" in spec["paths"]
    assert "/rpc/createEditorChart" not in spec["paths"]


def test_list_methods_contains_registered():
    app = FastAPI()
    register_rpc(app, "unitPing", _PingArgs, _PingResult, _ping)
    assert "unitPing" in list_methods()
