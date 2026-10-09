import json
import re
import time
from dataclasses import dataclass
from typing import Any

from app.clients.datalens_api import DatalensApiError
from app.formula.docs import select_fragments

OPEN_CHART = "Откройте чарт: формулы собираются по полям его датасета"
WIZARD_ONLY = "Формулы собираются по полям датасета wizard-чарта"
MANY_DATASETS = "У чарта несколько датасетов. Откройте чарт с одним датасетом"
CHART_DENIED = "Чарт недоступен"
DATASET_DENIED = "Датасет чарта недоступен"
DATASET_TOUCHED = "Проверка затронула датасет, формула не показана"
BUILD_FAILED = "Формулу собрать не удалось"
NOT_A_FORMULA = "Ответ не содержит отдельной строки формулы"
DB_CALL_DENIED = "Функции DB_CALL недоступны"

_DB_CALL = re.compile(r"\bDB_CALL_\w*", re.IGNORECASE)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_SYSTEM = (
    "Ответь одним JSON-объектом {\"explanation\",\"formula\"}. "
    "formula — строка формулы или null. "
    "Не пиши формулу внутри explanation."
)


@dataclass
class FormulaOutcome:
    reply: str
    stop_reason: str
    prompt_tokens: int
    completion_tokens: int
    rounds: int
    dataset_id: str | None


def _done(
    reply: str,
    stop_reason: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    rounds: int = 0,
    dataset_id: str | None = None,
) -> FormulaOutcome:
    return FormulaOutcome(
        reply=reply,
        stop_reason=stop_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        rounds=rounds,
        dataset_id=dataset_id,
    )


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _shared(body: dict) -> dict:
    raw = _dict(body.get("data")).get("shared")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return _dict(raw)


def _dataset_ids(chart: dict) -> list[str]:
    raw = _shared(chart).get("datasetsIds")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item]


def _schema(body: dict) -> list[dict]:
    raw = _dict(body.get("dataset")).get("result_schema")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _fingerprint(body: dict) -> tuple[Any, tuple]:
    rows = [
        (item.get("guid"), item.get("title"), item.get("formula") or item.get("source") or "")
        for item in _schema(body)
    ]
    rows.sort(key=lambda row: tuple("" if part is None else str(part) for part in row))
    return (body.get("mtime"), tuple(rows))


def _workbook_id(body: dict) -> str | None:
    value = body.get("workbookId")
    if value is None:
        return None
    return str(value)


def _field_line(item: dict) -> str:
    hidden = "true" if item.get("hidden") is True else "false"
    existing = item.get("formula") or item.get("source") or ""
    marker = "да" if existing else "нет"
    return (
        f"- {item.get('title')}: type={item.get('type')}, data_type={item.get('data_type')}, "
        f"aggregation={item.get('aggregation')}, formula={marker}, hidden: {hidden}"
    )


def _clean_explanation(explanation: str, formula: str) -> str:
    text = _FENCE.sub("", explanation)
    if formula:
        text = text.replace(formula, "")
    return text.strip()


def _without_rejected(text: str, rejected: list[str]) -> str:
    for item in sorted({item for item in rejected if item}, key=len, reverse=True):
        text = text.replace(item, "")
    return text.strip()


def _parse(content: str | None) -> tuple[str, str] | None:
    if not content:
        return None
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    explanation = obj.get("explanation")
    formula = obj.get("formula")
    if explanation is None:
        explanation = ""
    if not isinstance(explanation, str):
        return None
    if formula is None:
        formula_text = ""
    elif isinstance(formula, str):
        formula_text = formula.strip()
    else:
        return None
    cleaned = _clean_explanation(explanation, formula_text)
    if not cleaned:
        return None
    return cleaned, formula_text


def _accepted(explanation: str, formula: str) -> str:
    return f"{explanation}\n\n```\n{formula}\n```"


def _prompt(question: str, fixed: str, fragments: list, fields: str) -> str:
    parts = [fixed, "Поля датасета:", fields, f"Вопрос: {question}"]
    for item in fragments:
        parts.append(f"# {item.title}\n{item.body}")
    return "\n\n".join(part for part in parts if part)


def _messages(history: list, user: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": _SYSTEM}]
    for item in history or []:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            continue
        messages.append({"role": str(item["role"]), "content": str(item.get("content") or "")})
    messages.append({"role": "user", "content": user})
    return messages


async def _load_chart(api, chart_id: str) -> dict | FormulaOutcome:
    try:
        body = await api.rpc("getWizardChart", {"chartId": chart_id})
    except DatalensApiError as exc:
        if exc.status_code >= 500:
            raise
        return _done(CHART_DENIED, "blocked")
    if not isinstance(body, dict):
        return _done(CHART_DENIED, "blocked")
    return body


async def _load_dataset(api, dataset_id: str) -> dict | FormulaOutcome:
    try:
        body = await api.rpc("getDataset", {"datasetId": dataset_id})
    except DatalensApiError as exc:
        if exc.status_code >= 500:
            raise
        return _done(DATASET_DENIED, "blocked")
    if not isinstance(body, dict):
        return _done(DATASET_DENIED, "blocked")
    return body


async def _confirm(api, dataset_id: str, fingerprint: tuple) -> FormulaOutcome | None:
    try:
        body = await api.rpc("getDataset", {"datasetId": dataset_id})
    except DatalensApiError as exc:
        if exc.status_code >= 500:
            raise
        return _done(DATASET_DENIED, "blocked", dataset_id=dataset_id)
    if not isinstance(body, dict) or _fingerprint(body) != fingerprint:
        return _done(DATASET_TOUCHED, "blocked", dataset_id=dataset_id)
    return None


async def run_formula_turn(
    *,
    llm,
    api,
    pack,
    docs,
    question,
    chart_id,
    chart_kind,
    history,
    attempts,
    fragment_limit,
    fragment_chars,
    deadline_at,
) -> FormulaOutcome:
    if not chart_id:
        return _done(OPEN_CHART, "blocked")
    if chart_kind == "ql":
        return _done(WIZARD_ONLY, "blocked")

    chart = await _load_chart(api, chart_id)
    if isinstance(chart, FormulaOutcome):
        return chart
    if str(chart.get("type") or "").endswith("_ql_node"):
        return _done(WIZARD_ONLY, "blocked")
    dataset_ids = _dataset_ids(chart)
    if not dataset_ids:
        return _done(WIZARD_ONLY, "blocked")
    if len(dataset_ids) > 1:
        return _done(MANY_DATASETS, "blocked")
    if not pack.in_scope(_workbook_id(chart)):
        return _done(CHART_DENIED, "blocked")

    dataset = await _load_dataset(api, dataset_ids[0])
    if isinstance(dataset, FormulaOutcome):
        return dataset
    dataset_id = str(dataset.get("id") or dataset_ids[0])
    if not pack.in_scope(_workbook_id(dataset)):
        return _done(DATASET_DENIED, "blocked", dataset_id=dataset_id)

    fingerprint = _fingerprint(dataset)
    fixed, fragments = docs
    chosen = select_fragments(
        question, list(fragments), limit=fragment_limit, max_chars=fragment_chars
    )
    fields = "\n".join(_field_line(item) for item in _schema(dataset))
    messages = _messages(history, _prompt(question, fixed, chosen, fields))
    prompt_tokens = 0
    completion_tokens = 0
    rounds = 0
    last_error = NOT_A_FORMULA
    rejected: list[str] = []

    for _attempt in range(attempts):
        if time.monotonic() >= deadline_at:
            return _done(
                BUILD_FAILED,
                "deadline",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                rounds=rounds,
                dataset_id=dataset_id,
            )
        response = await llm.chat(messages, None, tool_choice="none")
        rounds += 1
        prompt_tokens += int(response.prompt_tokens or 0)
        completion_tokens += int(response.completion_tokens or 0)
        parsed = _parse(response.content)
        messages.append({"role": "assistant", "content": response.content or ""})
        if parsed is None:
            last_error = NOT_A_FORMULA
            messages.append({"role": "user", "content": last_error})
            continue
        explanation, formula = parsed
        if not formula:
            return _done(
                _without_rejected(explanation, rejected),
                "explanation",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                rounds=rounds,
                dataset_id=dataset_id,
            )
        if _DB_CALL.search(formula):
            rejected.append(formula)
            last_error = DB_CALL_DENIED
            messages.append({"role": "user", "content": f"{last_error}\n{formula}"})
            continue
        try:
            result = await api.rpc(
                "validateDatasetFormula", {"datasetId": dataset_id, "formula": formula}
            )
        except DatalensApiError as exc:
            if exc.status_code != 400:
                raise
            changed = await _confirm(api, dataset_id, fingerprint)
            if changed is not None:
                return _done(
                    changed.reply,
                    changed.stop_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    rounds=rounds,
                    dataset_id=dataset_id,
                )
            last_error = exc.message or NOT_A_FORMULA
            rejected.append(formula)
            messages.append({"role": "user", "content": f"{last_error}\n{formula}"})
            continue
        changed = await _confirm(api, dataset_id, fingerprint)
        if changed is not None:
            return _done(
                changed.reply,
                changed.stop_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                rounds=rounds,
                dataset_id=dataset_id,
            )
        if isinstance(result, dict) and result.get("valid") is True:
            return _done(
                _accepted(_without_rejected(explanation, rejected), formula),
                "formula",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                rounds=rounds,
                dataset_id=dataset_id,
            )
        rejected.append(formula)
        last_error = NOT_A_FORMULA
        messages.append({"role": "user", "content": f"{last_error}\n{formula}"})

    visible_error = _without_rejected(last_error, rejected)
    reply = f"{BUILD_FAILED}\n{visible_error}" if visible_error else BUILD_FAILED
    return _done(
        reply,
        "rejected",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        rounds=rounds,
        dataset_id=dataset_id,
    )
