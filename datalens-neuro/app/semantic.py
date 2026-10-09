import re
from typing import Any

from app.packs import Pack

_HIDDEN_INTENT_KEYS = {"sql_hint", "table", "triggers"}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def public_intent(intent_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    return {"id": intent_id, **{k: v for k, v in spec.items() if k not in _HIDDEN_INTENT_KEYS}}


def _dedupe(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    out = []
    for item in items:
        if item.get(key) in seen:
            continue
        seen.add(item.get(key))
        out.append(item)
    return out


def search(pack: Pack, query: str, limit: int = 8) -> dict[str, Any]:
    q = _norm(query)
    synonyms = pack.glossary.get("synonyms") or {}
    intents = pack.glossary.get("intents") or {}

    terms = []
    for term, values in synonyms.items() if isinstance(synonyms, dict) else []:
        variants = [_norm(term)] + [_norm(v) for v in (values or [])]
        if any(v and (v in q or q in v) for v in variants):
            terms.append({"term": term, "synonyms": list(values or [])})

    matched_intents = []
    for intent_id, spec in intents.items() if isinstance(intents, dict) else []:
        if not isinstance(spec, dict):
            continue
        triggers = [_norm(t) for t in (spec.get("triggers") or [])]
        triggers += [_norm(spec.get("description")), _norm(intent_id)]
        if any(t and (t in q or q in t) for t in triggers):
            matched_intents.append(public_intent(intent_id, spec))

    words = {_norm(t["term"]) for t in terms} | {_norm(s) for t in terms for s in t["synonyms"]}
    words.discard("")

    datasets = [
        {"datasetId": card.get("entryId"), "name": card.get("name")}
        for name, card in pack.datasets_by_name.items()
        if q and (q in name or name in q or any(w in name for w in words))
    ]

    fields = []
    for card in pack.datasets_by_id.values():
        for item in card.get("fields") or []:
            title, guid = _norm(item.get("title")), _norm(item.get("guid"))
            if (len(title) >= 3 and (title in q or title in words)) or (guid and guid in words):
                fields.append(
                    {
                        "datasetId": card.get("entryId"),
                        "datasetName": card.get("name"),
                        "field": item.get("title"),
                        "guid": item.get("guid"),
                        "type": item.get("type"),
                    }
                )

    return {
        "query": query,
        "terms": terms[:limit],
        "intents": matched_intents[:limit],
        "datasets": _dedupe(datasets, "datasetId")[:limit],
        "fields": fields[: limit * 2],
        "businessRules": list(pack.glossary.get("business_rules") or [])[:8],
        "availableIntents": sorted(intents) if isinstance(intents, dict) else [],
    }


def get_intent(pack: Pack, intent_id: str) -> dict[str, Any] | None:
    spec = (pack.glossary.get("intents") or {}).get(intent_id)
    return public_intent(intent_id, spec) if isinstance(spec, dict) else None
