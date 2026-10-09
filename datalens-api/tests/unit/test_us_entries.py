import json

import httpx
import pytest
import respx

from app.errors import ApiError
from app.us_entries import create_and_publish_entry

US_HOST = "http://us.example:8080"


@pytest.mark.asyncio
@respx.mock
async def test_create_and_publish_posts_then_publishes():
    create = respx.post(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(200, json={"entryId": "abc", "publishedId": None})
    )
    publish = respx.post(f"{US_HOST}/private/entries/abc").mock(
        return_value=httpx.Response(200, json={"entryId": "abc", "publishedId": "rev1"})
    )
    result = await create_and_publish_entry({"scope": "widget", "data": {"x": 1}})
    assert result["publishedId"] == "rev1"
    assert create.called
    assert json.loads(publish.calls[0].request.content) == {
        "mode": "publish",
        "data": {"x": 1},
    }


@pytest.mark.asyncio
@respx.mock
async def test_create_and_publish_missing_entry_id():
    respx.post(f"{US_HOST}/private/entries").mock(
        return_value=httpx.Response(200, json={"scope": "widget"})
    )
    with pytest.raises(ApiError) as exc:
        await create_and_publish_entry({"data": {}})
    assert exc.value.status_code == 500
    assert "entryId" in exc.value.message
