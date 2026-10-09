import json
from datetime import datetime
from typing import Any

from app.packs import Pack

_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

CORE_RULES = """Ты — аналитический ассистент по DataLens. Ты только читаешь данные и метаданные: создавать или менять дашборды, чарты и датасеты не можешь. Если об этом просят — так и скажи.

Правила:
- Отвечай на языке вопроса, кратко, в Markdown.
- Числа бери только из результатов инструментов. Не придумывай цифры, id сущностей и названия полей.
- Всегда называй период, фильтры и источник (датасет или чарт), по которым посчитан ответ.
- Порядок работы: найди сущность (semantic_search, list_workbook_entries, get_dashboard) → посмотри поля (get_dataset) → посчитай (query_dataset) или возьми данные чарта (get_chart_data).
- Точные значения для фильтров уточняй через get_dataset_field_values: «Москва» может храниться как «г. Москва».
- Если get_chart_data вернул DEADLINE_EXCEEDED (тяжёлый чарт) — посчитай через query_dataset с фильтрами и меньшим числом полей.
- Если get_chart_data вернул normalized: false — посчитай через query_dataset по datasetIds.
- Если инструмент вернул ошибку — исправь аргументы по тексту ошибки, не повторяй тот же вызов.
- Не выводи токены, пароли и большие JSON-конфиги."""

FINAL_ANSWER_INSTRUCTION = (
    "Лимит шагов исчерпан. Не вызывай инструменты. Ответь по уже полученным данным "
    "и прямо скажи, чего не хватило для полного ответа."
)


def build_system_prompt(pack: Pack, *, context: dict[str, Any] | None, now: datetime) -> str:
    parts = [
        CORE_RULES,
        f"Сейчас: {now:%Y-%m-%d %H:%M} ({_WEEKDAYS[now.weekday()]}), часовой пояс {now.tzname() or 'UTC'}.",
    ]
    if pack.workbook_ids:
        parts.append(
            "Доступные воркбуки: " + ", ".join(pack.workbook_ids) + ". Сущности из других воркбуков недоступны."
        )
    if pack.prompt:
        parts.append(f"Правила предметной области ({pack.title or pack.name}):\n{pack.prompt}")
    if context:
        opened = "Что открыто у пользователя: " + json.dumps(context, ensure_ascii=False)
        dashboard_id = context.get("dashboardId")
        chart_id = context.get("chartId")
        tab_id = context.get("tabId")
        if dashboard_id and tab_id:
            opened += (
                f"\nВопрос про «эту страницу», «этот дашборд» и «здесь» относится к дашборду {dashboard_id}, "
                f"вкладка {tab_id}. Сначала вызови get_dashboard с этим id и смотри эту вкладку."
            )
        elif dashboard_id:
            opened += (
                f"\nВопрос про «эту страницу», «этот дашборд» и «здесь» относится к дашборду {dashboard_id}. "
                "В адресе вкладка не указана: открыта первая вкладка. Сначала вызови get_dashboard с этим id."
            )
        elif chart_id:
            opened += (
                f"\nВопрос про «эту страницу» и «этот чарт» относится к чарту {chart_id}. "
                "Сначала вызови get_chart с этим id."
            )
        params = context.get("params") or {}
        if params:
            opened += (
                "\nparams — текущие значения селекторов страницы, они важнее значений по умолчанию в get_dashboard. "
                "Строка __interval_НАЧАЛО_КОНЕЦ — выбранный период. Пустые селекторы сюда не попадают."
            )
        elif dashboard_id:
            opened += "\nСелекторы страницы на значениях по умолчанию из get_dashboard."
        parts.append(opened)
    return "\n\n".join(parts)
