import os

import pytest

TEST_ENV = {
    "NEURO_API_TOKEN": "test-neuro-token",
    "NEURO_ENABLED": "true",
    "NEURO_UI_ENABLED": "false",
    "NEURO_DEFAULT_PACK": "default",
    "NEURO_PACKS_DIR": "/app/packs",
    "NEURO_DB_PATH": "/tmp/neuro-test.sqlite",
    "NEURO_RATE_LIMIT_PER_MIN": "30",
    "DATALENS_API_HOST": "http://datalens-api.example:8393",
    "DL_API_TOKEN": "test-dl-api-token",
    "LLM_PROVIDER": "openai_compatible",
    "LLM_BASE_URL": "http://llm.example/v1",
    "LLM_MODEL": "test-model",
    "LLM_API_KEY": "test-llm-key",
}

for _key, _value in TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("NEURO_DB_PATH", str(tmp_path / "neuro.sqlite"))
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
