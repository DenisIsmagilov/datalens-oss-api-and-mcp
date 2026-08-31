import json
from typing import Any


def tool_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
