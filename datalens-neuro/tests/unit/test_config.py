from app.config import get_settings


def test_defaults_and_llm_configured(monkeypatch):
    settings = get_settings()
    assert settings.neuro_port == 8396
    assert settings.neuro_max_rounds == 15
    assert settings.neuro_deadline_sec == 150
    assert settings.neuro_timezone == "Europe/Moscow"
    assert settings.llm_configured is True
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    assert get_settings().llm_configured is False


def test_bool_switches(monkeypatch):
    monkeypatch.setenv("NEURO_ENABLED", "false")
    monkeypatch.setenv("NEURO_UI_ENABLED", "true")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.neuro_enabled is False
    assert settings.neuro_ui_enabled is True
    assert settings.neuro_ui_title == "Нейроаналитик"
    monkeypatch.setenv("NEURO_UI_TITLE", "  ")
    get_settings.cache_clear()
    assert get_settings().neuro_ui_title == "Нейроаналитик"
