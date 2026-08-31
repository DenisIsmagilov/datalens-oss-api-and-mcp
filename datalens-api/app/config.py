from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    dl_api_token: str
    us_master_token: str
    us_host: str = "http://us:8080"
    control_api_host: str = "http://control-api:8080"
    meta_manager_host: str = "http://meta-manager:8080"
    ui_api_host: str = "http://ui-api:8080"
    datalens_api_port: int = 8393
    datalens_api_version_default: str = "2"
    us_tenant_id: str = "common"
    auth_host: str = "http://auth:8080"
    auth_login: str = "admin"
    auth_password: str = "admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
