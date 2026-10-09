"""Прогон вопросов через /v1/chat; отчёт для ручной оценки сохраняется в /data/eval/<run_id>.md.

Запуск на проде: docker exec datalens-neuro python scripts/eval.py [questions.yaml]
"""
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

_DEFAULT_QUESTIONS = Path(__file__).with_name("eval_questions.yaml")


def load_questions(path: Path) -> list[dict[str, Any]]:
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = spec.get("questions") if isinstance(spec, dict) else None
    if not isinstance(questions, list):
        raise ValueError(f"{path}: 'questions' must be a list")
    return questions


def _cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def render_report(rows: list[dict[str, Any]], run_id: str) -> str:
    lines = [
        f"# Eval {run_id}",
        "",
        "| # | Вопрос | HTTP | stopReason | Инструменты | Время, с | Токены |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['index']}.{row['turn']} | {_cell(row['question'])} | {row['http']} | {row['stopReason']} "
            f"| {_cell(', '.join(row['tools']) or '-')} | {row['seconds']:.1f} | {row['tokens']} |"
        )
    lines.append("")
    for row in rows:
        lines += [f"## {row['index']}.{row['turn']} {row['question']}", "", row["reply"] or "(нет ответа)", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else _DEFAULT_QUESTIONS
    questions = load_questions(path)
    base_url = os.environ.get("NEURO_EVAL_URL", f"http://localhost:{os.environ.get('NEURO_PORT', '8396')}")
    headers = {"Authorization": f"Bearer {os.environ['NEURO_API_TOKEN']}"}
    run_id = time.strftime("eval-%Y%m%d_%H%M%S")
    rows: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url, timeout=300) as client:
        for index, item in enumerate(questions, 1):
            conversation_id = None
            for turn, message in enumerate(item["messages"], 1):
                payload: dict[str, Any] = {"message": message, "user": {"externalId": run_id}}
                if item.get("pack"):
                    payload["pack"] = item["pack"]
                if conversation_id:
                    payload["conversationId"] = conversation_id
                started = time.monotonic()
                response = client.post(
                    "/v1/chat", json=payload, headers={**headers, "x-request-id": f"{run_id}-{index}-{turn}"}
                )
                body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                conversation_id = body.get("conversationId", conversation_id)
                usage = body.get("usage") or {}
                rows.append(
                    {
                        "index": index,
                        "turn": turn,
                        "question": message,
                        "http": response.status_code,
                        "stopReason": body.get("stopReason", body.get("code", "-")),
                        "tools": [f"{s['tool']}:{s['status']}" for s in body.get("steps") or []],
                        "seconds": time.monotonic() - started,
                        "tokens": usage.get("promptTokens", 0) + usage.get("completionTokens", 0),
                        "reply": body.get("reply", ""),
                    }
                )
                print(f"{index}.{turn} http={response.status_code} stop={rows[-1]['stopReason']} t={rows[-1]['seconds']:.1f}s", flush=True)
    report = render_report(rows, run_id)
    out_dir = Path(os.environ.get("NEURO_EVAL_DIR", "/data/eval"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
