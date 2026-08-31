import os

import pytest

os.environ.setdefault("MCP_AUTH_TOKEN", "test-mcp-token")
os.environ.setdefault("DL_API_TOKEN", "test-dl-token")
os.environ.setdefault("DATALENS_API_HOST", "http://datalens-api.example:8393")
os.environ.setdefault("DATALENS_MCP_PORT", "8394")
os.environ.setdefault("DATALENS_API_VERSION", "2")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: read-only tests against a reachable DataLens API",
    )
