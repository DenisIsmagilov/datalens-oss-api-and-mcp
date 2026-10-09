from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.prompt import CORE_RULES, build_system_prompt
from app.packs import Pack

NOW = datetime(2026, 10, 7, 14, 30, tzinfo=ZoneInfo("Europe/Moscow"))


def test_prompt_with_pack_and_context():
    pack = Pack(name="demo", title="Demo", workbook_ids=["wb1"], prompt="Каналы: north, south.")
    prompt = build_system_prompt(pack, context={"dashboardId": "d1"}, now=NOW)
    assert prompt.startswith(CORE_RULES)
    assert "Сейчас: 2026-10-07 14:30 (среда), часовой пояс MSK." in prompt
    assert "Доступные воркбуки: wb1." in prompt
    assert "Правила предметной области (Demo):\nКаналы: north, south." in prompt
    assert 'Что открыто у пользователя: {"dashboardId": "d1"}' in prompt
    assert "относится к дашборду d1" in prompt
    assert "открыта первая вкладка" in prompt
    assert "значениях по умолчанию" in prompt


def test_prompt_for_default_pack():
    prompt = build_system_prompt(Pack(name="default", title="", workbook_ids=[]), context=None, now=NOW)
    assert "Доступные воркбуки" not in prompt
    assert "Правила предметной области" not in prompt
    assert "Что открыто" not in prompt
