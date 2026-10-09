from typing import Any

from app.clients.us import get_us_client
from app.errors import ApiError


async def create_and_publish_entry(create_body: dict[str, Any]) -> Any:
    """Create a US entry, then publish the same data so UI loads it."""
    created = await get_us_client().request("POST", "/private/entries", json=create_body)
    if not isinstance(created, dict) or not created.get("entryId"):
        raise ApiError(500, "INTERNAL", "US create did not return entryId")
    return await get_us_client().request(
        "POST",
        f"/private/entries/{created['entryId']}",
        json={"mode": "publish", "data": create_body["data"]},
    )
