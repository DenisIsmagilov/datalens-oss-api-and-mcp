import time
from collections.abc import Callable

_MAX_ITEMS = 10000


class ScopeCache:
    def __init__(self, ttl_sec: float = 600.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl_sec = ttl_sec
        self._clock = clock
        self._items: dict[str, tuple[str, float]] = {}

    def get(self, entry_id: str) -> str | None:
        item = self._items.get(entry_id)
        if item is None:
            return None
        if item[1] < self._clock():
            self._items.pop(entry_id, None)
            return None
        return item[0]

    def put(self, entry_id: str, workbook_id: str | None) -> None:
        if len(self._items) >= _MAX_ITEMS:
            self._items.clear()
        self._items[entry_id] = (workbook_id or "", self._clock() + self._ttl_sec)
