import os

import pytest

os.environ.setdefault("DL_API_TOKEN", "test-dl-api-token")
os.environ.setdefault("US_MASTER_TOKEN", "test-us-master-token")
os.environ.setdefault("US_HOST", "http://us.example:8080")
os.environ.setdefault("CONTROL_API_HOST", "http://control-api.example:8080")
os.environ.setdefault("META_MANAGER_HOST", "http://meta-manager.example:8080")
os.environ.setdefault("UI_API_HOST", "http://ui-api.example:8080")
os.environ.setdefault("DATA_API_HOST", "http://data-api.example:8080")
os.environ.setdefault("CHARTS_HOST", "http://ui.example:8080")
os.environ.setdefault("DATALENS_API_PORT", "8393")
os.environ.setdefault("DATALENS_API_VERSION_DEFAULT", "2")
os.environ.setdefault("US_TENANT_ID", "common")
os.environ.setdefault("AUTH_HOST", "http://auth.example:8080")
os.environ.setdefault("AUTH_LOGIN", "admin")
os.environ.setdefault("AUTH_PASSWORD", "admin")


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("DL_API_TOKEN", "test-dl-api-token")
    monkeypatch.setenv("US_MASTER_TOKEN", "test-us-master-token")
    monkeypatch.setenv("US_HOST", "http://us.example:8080")
    monkeypatch.setenv("CONTROL_API_HOST", "http://control-api.example:8080")
    monkeypatch.setenv("META_MANAGER_HOST", "http://meta-manager.example:8080")
    monkeypatch.setenv("UI_API_HOST", "http://ui-api.example:8080")
    monkeypatch.setenv("DATA_API_HOST", "http://data-api.example:8080")
    monkeypatch.setenv("CHARTS_HOST", "http://ui.example:8080")
    monkeypatch.setenv("DATALENS_API_PORT", "8393")
    monkeypatch.setenv("DATALENS_API_VERSION_DEFAULT", "2")
    monkeypatch.setenv("US_TENANT_ID", "common")
    monkeypatch.setenv("AUTH_HOST", "http://auth.example:8080")
    monkeypatch.setenv("AUTH_LOGIN", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "admin")
    from app.clients.auth import invalidate_user_access_token
    from app.config import get_settings

    get_settings.cache_clear()
    invalidate_user_access_token()
