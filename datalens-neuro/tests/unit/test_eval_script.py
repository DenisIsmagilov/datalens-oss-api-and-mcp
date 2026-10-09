from pathlib import Path

from scripts.eval import load_questions, render_report


def test_bundled_questions_are_valid():
    questions = load_questions(Path("/app/scripts/eval_questions.yaml"))
    assert len(questions) == 2
    assert all(q["messages"] and all(isinstance(m, str) and m for m in q["messages"]) for q in questions)


def test_render_report():
    rows = [
        {"index": 1, "turn": 1, "question": "Сколько | заказов?", "http": 200, "stopReason": "answer", "tools": ["query_dataset:OK"], "seconds": 3.21, "tokens": 900, "reply": "Ответ"},
        {"index": 2, "turn": 1, "question": "Ошибка", "http": 502, "stopReason": "-", "tools": [], "seconds": 0.1, "tokens": 0, "reply": ""},
    ]
    report = render_report(rows, "eval-1")
    assert report.startswith("# Eval eval-1")
    assert "| 1.1 | Сколько / заказов? | 200 | answer | query_dataset:OK | 3.2 | 900 |" in report
    assert "## 1.1 Сколько | заказов?\n\nОтвет" in report
