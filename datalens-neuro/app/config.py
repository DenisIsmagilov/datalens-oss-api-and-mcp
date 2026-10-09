from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    neuro_enabled: bool = True
    neuro_ui_enabled: bool = False
    neuro_port: int = 8396
    neuro_api_token: str = ""
    neuro_default_pack: str = "default"
    neuro_packs_dir: str = "/packs"
    neuro_db_path: str = "/data/neuro.sqlite"
    neuro_timezone: str = "Europe/Moscow"
    neuro_history_messages: int = 10
    neuro_max_rounds: int = 15
    neuro_deadline_sec: float = 150.0
    neuro_formula_attempts: int = 3
    neuro_formula_doc_fragments: int = 8
    neuro_formula_doc_chars: int = 6000
    neuro_tool_result_max_chars: int = 12000
    neuro_conversation_ttl_days: int = 30
    neuro_rate_limit_per_min: int = 30
    datalens_api_host: str = "http://datalens-api:8393"
    dl_api_token: str = ""
    datalens_api_timeout_sec: float = 90.0
    llm_provider: str = "openai_compatible"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_sec: float = 120.0
    llm_max_retries: int = 2
    neuro_ui_title: str = "Нейроаналитик"
    neuro_ui_roles: str = "datalens.admin,datalens.editor"
    neuro_ui_origins: str = "http://127.0.0.1:8080"
    neuro_ui_conversation_idle_hours: int = 6
    auth_token_public_key: str = ""

    @field_validator("neuro_ui_title")
    @classmethod
    def _ui_title(cls, value: str) -> str:
        text = value.strip()
        return (text or "Нейроаналитик")[:80]

    @property
    def ui_roles(self) -> frozenset[str]:
        return frozenset(part.strip() for part in self.neuro_ui_roles.split(",") if part.strip())

    @property
    def ui_origins(self) -> frozenset[str]:
        return frozenset(part.strip() for part in self.neuro_ui_origins.split(",") if part.strip())

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model and self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
