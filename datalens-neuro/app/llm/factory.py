import logging

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger("datalens_neuro.llm")

_PROVIDERS = {"openai_compatible", "openai"}


def build_llm(settings: Settings) -> LLMProvider | None:
    if not settings.llm_configured:
        return None
    if settings.llm_provider not in _PROVIDERS:
        logger.warning("unsupported LLM_PROVIDER=%s", settings.llm_provider)
        return None
    return OpenAICompatibleProvider(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
        timeout_sec=settings.llm_timeout_sec,
        max_retries=settings.llm_max_retries,
    )
