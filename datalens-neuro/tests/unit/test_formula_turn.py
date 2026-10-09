import copy
import json
import time

import pytest

from app.clients.datalens_api import DatalensApiError
from app.formula.turn import run_formula_turn
from app.packs import Pack
from tests.fakes import ScriptedLLM, text


DATASET = {
    "id": "ds123ds123ds1",
    "mtime": "t1",
    "workbookId": "wb1",
    "dataset": {"result_schema": [
        {"guid": "g1", "title": "Выручка", "type": "MEASURE", "data_type": "float", "aggregation": "sum"},
    ]},
}
CHART = {"entryId": "ch123ch123ch1", "workbookId": "wb1", "type": "graph_wizard_node", "data": {"shared": {"datasetsIds": ["ds123ds123ds1"]}}}

PACK = Pack(name="demo", title="", workbook_ids=["wb1"])

OPEN_CHART = "Откройте чарт: формулы собираются по полям его датасета"
WIZARD_ONLY = "Формулы собираются по полям датасета wizard-чарта"
MANY_DATASETS = "У чарта несколько датасетов. Откройте чарт с одним датасетом"
CHART_DENIED = "Чарт недоступен"
DATASET_DENIED = "Датасет чарта недоступен"
DATASET_TOUCHED = "Проверка затронула датасет, формула не показана"
BUILD_FAILED = "Формулу собрать не удалось"
NOT_A_FORMULA = "Ответ не содержит отдельной строки формулы"
DB_CALL_DENIED = "Функции DB_CALL недоступны"


class FakeApi:
    def __init__(self, bodies=None, errors=None, queues=None):
        self.bodies = bodies or {}
        self.errors = errors or {}
        self.queues = {key: list(value) for key, value in (queues or {}).items()}
        self.calls = []

    async def rpc(self, method, args):
        self.calls.append((method, args))
        if method in self.errors:
            raise self.errors[method]
        if method in self.queues:
            item = self.queues[method].pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return self.bodies[method]


def _turn(llm, api, **kw):
    params = dict(
        llm=llm, api=api, pack=PACK, docs=("Поле пишется как [Заголовок].", []),
        question="прирост", chart_id="ch123ch123ch1", chart_kind="wizard", history=[],
        attempts=3, fragment_limit=8, fragment_chars=6000, deadline_at=time.monotonic() + 30,
    )
    params.update(kw)
    return run_formula_turn(**params)


def _happy_api(**extra):
    bodies = {"getWizardChart": CHART, "getDataset": DATASET, "validateDatasetFormula": {"valid": True}}
    bodies.update(extra.pop("bodies", {}))
    return FakeApi(bodies=bodies, **extra)


def _blocks(reply: str) -> list[str]:
    lines = reply.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index] == "```":
            chunk: list[str] = []
            index += 1
            while index < len(lines) and lines[index] != "```":
                chunk.append(lines[index])
                index += 1
            if index >= len(lines):
                break
            blocks.append("\n".join(chunk))
        index += 1
    return blocks


def _formula(explanation: str, formula: str) -> str:
    return json.dumps({"explanation": explanation, "formula": formula}, ensure_ascii=False)


async def test_missing_chart_does_not_call_model():
    llm = ScriptedLLM([])
    api = FakeApi()
    outcome = await _turn(llm, api, chart_id="")
    assert outcome.reply == OPEN_CHART
    assert outcome.stop_reason == "blocked"
    assert outcome.dataset_id is None
    assert llm.calls == []


async def test_ql_kind_does_not_call_api():
    llm = ScriptedLLM([])
    api = FakeApi()
    outcome = await _turn(llm, api, chart_kind="ql")
    assert outcome.reply == WIZARD_ONLY
    assert outcome.stop_reason == "blocked"
    assert api.calls == []


async def test_ql_node_type_uses_wizard_phrase():
    chart = copy.deepcopy(CHART)
    chart["type"] = "graph_ql_node"
    llm = ScriptedLLM([])
    api = FakeApi(bodies={"getWizardChart": chart})
    outcome = await _turn(llm, api)
    assert outcome.reply == WIZARD_ONLY
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_empty_datasets_use_wizard_phrase():
    chart = copy.deepcopy(CHART)
    chart["data"]["shared"]["datasetsIds"] = []
    llm = ScriptedLLM([])
    api = FakeApi(bodies={"getWizardChart": chart})
    outcome = await _turn(llm, api)
    assert outcome.reply == WIZARD_ONLY
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_shared_json_string_with_two_datasets():
    chart = copy.deepcopy(CHART)
    chart["data"]["shared"] = json.dumps({"datasetsIds": ["ds123ds123ds1", "ds223ds223ds2"]})
    llm = ScriptedLLM([])
    api = FakeApi(bodies={"getWizardChart": chart})
    outcome = await _turn(llm, api)
    assert outcome.reply == MANY_DATASETS
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_two_datasets_do_not_call_model():
    chart = copy.deepcopy(CHART)
    chart["data"]["shared"]["datasetsIds"] = ["ds123ds123ds1", "ds223ds223ds2"]
    llm = ScriptedLLM([])
    api = FakeApi(bodies={"getWizardChart": chart})
    outcome = await _turn(llm, api)
    assert outcome.reply == MANY_DATASETS
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_missing_chart_is_unavailable():
    llm = ScriptedLLM([])
    api = FakeApi(errors={"getWizardChart": DatalensApiError(404, "NOT_FOUND", "missing")})
    outcome = await _turn(llm, api)
    assert outcome.reply == CHART_DENIED
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_chart_outside_pack_is_unavailable():
    chart = copy.deepcopy(CHART)
    chart["workbookId"] = "wb-other"
    llm = ScriptedLLM([])
    api = FakeApi(bodies={"getWizardChart": chart})
    outcome = await _turn(llm, api)
    assert outcome.reply == CHART_DENIED
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_missing_dataset_is_unavailable():
    llm = ScriptedLLM([])
    api = FakeApi(
        bodies={"getWizardChart": CHART},
        errors={"getDataset": DatalensApiError(404, "NOT_FOUND", "missing")},
    )
    outcome = await _turn(llm, api)
    assert outcome.reply == DATASET_DENIED
    assert outcome.stop_reason == "blocked"
    assert outcome.dataset_id is None
    assert llm.calls == []


async def test_dataset_outside_pack_is_unavailable():
    dataset = {**DATASET, "workbookId": "wb-other"}
    llm = ScriptedLLM([])
    api = FakeApi(bodies={"getWizardChart": CHART, "getDataset": dataset})
    outcome = await _turn(llm, api)
    assert outcome.reply == DATASET_DENIED
    assert outcome.stop_reason == "blocked"
    assert llm.calls == []


async def test_accepted_formula_is_fenced_once_and_hidden_field_is_prompted():
    dataset = copy.deepcopy(DATASET)
    dataset["dataset"]["result_schema"].append({"guid": "g2", "title": "Скрытое", "hidden": True})
    same = copy.deepcopy(dataset)
    llm = ScriptedLLM([text(_formula("прирост", "SUM([Выручка])"))])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "validateDatasetFormula": {"valid": True}},
        queues={"getDataset": [dataset, same]},
    )
    outcome = await _turn(llm, api)
    blocks = _blocks(outcome.reply)
    assert blocks == ["SUM([Выручка])"]
    outside = outcome.reply.replace("```\nSUM([Выручка])\n```", "")
    assert "прирост" in outside
    assert "```" not in outside
    assert outcome.stop_reason == "formula"
    assert outcome.dataset_id == "ds123ds123ds1"
    assert outcome.rounds == 1
    assert outcome.prompt_tokens == 10
    assert outcome.completion_tokens == 5
    blob = json.dumps(llm.calls[0]["messages"], ensure_ascii=False)
    assert "Скрытое" in blob
    assert "hidden: true" in blob
    assert llm.calls[0]["tools"] is None
    assert llm.calls[0]["tool_choice"] == "none"
    assert api.calls[-1][0] == "getDataset"


async def test_second_attempt_replaces_rejected_formula():
    llm = ScriptedLLM([
        text(_formula("нет", "SUM([Нет])")),
        text(_formula("есть", "SUM([Выручка])")),
    ])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "getDataset": DATASET},
        queues={"validateDatasetFormula": [
            DatalensApiError(400, "INVALID_ARGUMENT", "неизвестное поле"),
            {"valid": True},
        ]},
    )
    outcome = await _turn(llm, api)
    assert "SUM([Выручка])" in outcome.reply
    assert "SUM([Нет])" not in outcome.reply
    assert outcome.stop_reason == "formula"
    notes = [
        message.get("content") or ""
        for message in llm.calls[1]["messages"]
        if message.get("role") == "user"
    ]
    assert any("SUM([Нет])" in note and "неизвестное поле" in note for note in notes)
    assert outcome.rounds == 2


async def test_three_rejections_hide_formula_text():
    llm = ScriptedLLM([text(_formula("x", "SUM([Нет])")) for _ in range(3)])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "getDataset": DATASET},
        queues={"validateDatasetFormula": [
            DatalensApiError(400, "INVALID_ARGUMENT", "неизвестное поле") for _ in range(3)
        ]},
    )
    outcome = await _turn(llm, api)
    assert outcome.reply.startswith(BUILD_FAILED)
    assert "неизвестное поле" in outcome.reply
    assert "SUM([Нет])" not in outcome.reply
    assert outcome.stop_reason == "rejected"
    assert len(llm.calls) == 3


async def test_validator_error_quoting_formula_is_stripped():
    message = "Cannot parse SUM([Нет])"
    llm = ScriptedLLM([text(_formula("x", "SUM([Нет])")) for _ in range(3)])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "getDataset": DATASET},
        queues={"validateDatasetFormula": [
            DatalensApiError(400, "INVALID_ARGUMENT", message) for _ in range(3)
        ]},
    )
    outcome = await _turn(llm, api)
    assert outcome.reply.startswith(BUILD_FAILED)
    assert "SUM([Нет])" not in outcome.reply
    assert outcome.stop_reason == "rejected"
    assert len(llm.calls) == 3


async def test_accepted_explanation_drops_earlier_rejected_formula():
    llm = ScriptedLLM([
        text(_formula("нет", "SUM([Нет])")),
        text(_formula("SUM([Нет]) не подходит", "SUM([Выручка])")),
    ])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "getDataset": DATASET},
        queues={"validateDatasetFormula": [
            DatalensApiError(400, "INVALID_ARGUMENT", "неизвестное поле"),
            {"valid": True},
        ]},
    )
    outcome = await _turn(llm, api)
    assert _blocks(outcome.reply) == ["SUM([Выручка])"]
    assert outcome.reply.count("SUM([Выручка])") == 1
    assert "SUM([Нет])" not in outcome.reply
    assert outcome.stop_reason == "formula"


async def test_three_unparsed_replies_name_the_parse_error():
    llm = ScriptedLLM([text("это не json") for _ in range(3)])
    api = _happy_api()
    outcome = await _turn(llm, api)
    assert NOT_A_FORMULA in outcome.reply
    assert outcome.reply.startswith(BUILD_FAILED)
    assert outcome.stop_reason == "rejected"
    assert not any(method == "validateDatasetFormula" for method, _args in api.calls)
    assert len(llm.calls) == 3


async def test_db_call_is_rejected_without_validator():
    formula = "DB_CALL_INT('x', [Выручка])"
    llm = ScriptedLLM([text(_formula("x", formula)) for _ in range(3)])
    api = _happy_api()
    outcome = await _turn(llm, api)
    assert DB_CALL_DENIED in outcome.reply
    assert formula not in outcome.reply
    assert outcome.stop_reason == "rejected"
    assert not any(method == "validateDatasetFormula" for method, _args in api.calls)
    assert len(llm.calls) == 3


async def test_deadline_before_attempt_skips_model():
    llm = ScriptedLLM([])
    api = _happy_api()
    outcome = await _turn(llm, api, deadline_at=time.monotonic() - 1)
    assert outcome.reply == BUILD_FAILED
    assert outcome.stop_reason == "deadline"
    assert llm.calls == []


async def test_changed_fingerprint_hides_accepted_formula():
    llm = ScriptedLLM([text(_formula("прирост", "SUM([Выручка])"))])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "validateDatasetFormula": {"valid": True}},
        queues={"getDataset": [DATASET, {**DATASET, "mtime": "t2"}]},
    )
    outcome = await _turn(llm, api)
    assert outcome.reply == DATASET_TOUCHED
    assert "SUM([Выручка])" not in outcome.reply
    assert outcome.stop_reason == "blocked"
    assert len(llm.calls) == 1


async def test_explanation_skips_validator():
    llm = ScriptedLLM([text('{"explanation":"поле Выручка уже суммируется","formula":null}')])
    api = _happy_api()
    outcome = await _turn(llm, api)
    assert outcome.stop_reason == "explanation"
    assert outcome.reply == "поле Выручка уже суммируется"
    assert not any(method == "validateDatasetFormula" for method, _args in api.calls)


async def test_validator_404_raises_without_retry():
    llm = ScriptedLLM([text(_formula("прирост", "SUM([Выручка])"))])
    api = FakeApi(
        bodies={"getWizardChart": CHART, "getDataset": DATASET},
        errors={"validateDatasetFormula": DatalensApiError(404, "NOT_FOUND", "draft missing")},
    )
    with pytest.raises(DatalensApiError) as caught:
        await _turn(llm, api)
    assert caught.value.status_code == 404
    assert len(llm.calls) == 1
    assert sum(method == "validateDatasetFormula" for method, _args in api.calls) == 1


async def test_dataset_5xx_propagates():
    llm = ScriptedLLM([])
    api = FakeApi(
        bodies={"getWizardChart": CHART},
        errors={"getDataset": DatalensApiError(502, "UNAVAILABLE", "down")},
    )
    with pytest.raises(DatalensApiError) as caught:
        await _turn(llm, api)
    assert caught.value.status_code == 502
    assert caught.value.message == "down"
