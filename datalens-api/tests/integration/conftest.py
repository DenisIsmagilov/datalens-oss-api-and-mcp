import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip()


_load_env_file(_REPO_ROOT / ".env.test")
_load_env_file(_REPO_ROOT / ".env.local")
os.environ.setdefault("DATALENS_API_BASE", "http://127.0.0.1:8393")
os.environ.setdefault("DL_API_TOKEN", "local-dl-api-token")


@pytest.fixture(autouse=True)
def _test_env():
    """Не подменять живые US/AUTH из корневого tests/conftest.py."""
    yield
