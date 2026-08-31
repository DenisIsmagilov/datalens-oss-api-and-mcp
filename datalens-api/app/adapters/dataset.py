from typing import Any

from app.models.generated import DatasetRead

_DATASET_READ_FIELDS = set(DatasetRead.model_fields)
_DROP_FIELDS = ("code", "message", "dataset_errors")


def _fill_result_schema(fields: Any) -> Any:
    if not isinstance(fields, list):
        return fields
    filled: list[Any] = []
    for field in fields:
        if not isinstance(field, dict):
            filled.append(field)
            continue
        item = dict(field)
        if item.get("calc_mode") == "direct" and "mode" not in item:
            item["mode"] = "direct"
        filled.append(item)
    return filled


def dataset_to_cloud(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    item = {key: value for key, value in raw.items() if key in _DATASET_READ_FIELDS}
    for key in _DROP_FIELDS:
        item.pop(key, None)
    dataset = item.get("dataset")
    if isinstance(dataset, dict) and "result_schema" in dataset:
        dataset = dict(dataset)
        dataset["result_schema"] = _fill_result_schema(dataset.get("result_schema"))
        item["dataset"] = dataset
    return item
