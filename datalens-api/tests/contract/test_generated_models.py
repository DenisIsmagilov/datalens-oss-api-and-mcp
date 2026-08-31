from app.models.generated import (
    CreateWorkbookArgs,
    GetWorkbooksListArgs,
    GetWorkbooksListResult,
)


def test_get_workbooks_list_args_accepts_cloud_payload():
    args = GetWorkbooksListArgs.model_validate(
        {"page": 0, "pageSize": 10, "orderField": "title", "orderDirection": "asc"}
    )
    assert getattr(args, "page_size", getattr(args, "pageSize", None)) == 10


def test_get_workbooks_list_result_requires_workbooks():
    result = GetWorkbooksListResult.model_validate({"workbooks": []})
    workbooks = getattr(result, "workbooks")
    assert workbooks == []
