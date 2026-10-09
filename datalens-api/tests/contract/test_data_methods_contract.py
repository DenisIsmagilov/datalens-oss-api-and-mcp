from fastapi.testclient import TestClient

from app.main import create_app


def _rpc_paths() -> list[str]:
    paths = TestClient(create_app()).get("/json/").json()["paths"]
    return [path for path in paths if path.startswith("/rpc/")]


def test_data_methods_published():
    paths = _rpc_paths()
    for method in ("queryDataset", "getDatasetFieldValues", "getChartData"):
        assert f"/rpc/{method}" in paths


def test_total_rpc_methods():
    assert len(_rpc_paths()) == 61
