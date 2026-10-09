from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_panel_script_has_root_and_no_token():
    text = (ROOT / "app/ui/loader.js").read_text(encoding="utf-8")
    assert "datalens-neuro-root" in text and "NEURO_API_TOKEN" not in text
    assert "/v1/ui/session" in text and "/v1/ui/chat" in text and "/v1/ui/new" in text
    assert "__NEURO_UI_TITLE_JSON__" in text
    assert 'if (/^[0-9a-z]{13}-/.test(segment)) return segment.slice(0, 13);' in text
    assert 'event.key === "Enter" && !event.shiftKey' in text
    assert "/gateway/root/us/getDashState" in text and "__meta__" in text
    assert "hashStates" in text and "function pageStore" in text
    assert ">Формулы</button>" in text
    assert "/v1/ui/formula" in text
    assert "/v1/ui/formula/thread" in text and "/v1/ui/formula/new" in text
    assert "datalens-neuro-formula" in text
    assert "chartKind" in text
    assert "Опишите формулу или вставьте её" in text
