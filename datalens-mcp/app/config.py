from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)

    mcp_auth_token: str
    dl_api_token: str
    datalens_api_host: str = "http://datalens-api:8393"
    datalens_mcp_port: int = 8394
    datalens_api_version: str = "2"
    datalens_api_timeout_sec: float = 90.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
