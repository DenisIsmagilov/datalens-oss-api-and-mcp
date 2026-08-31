from app.models.rpc_bi import EmptyResult, GetConnectionArgs


def test_get_connection_args_requires_id():
    args = GetConnectionArgs.model_validate({"connectionId": "abc"})
    assert args.connectionId == "abc"


def test_empty_result_is_empty_object():
    assert EmptyResult().model_dump() == {}
