from typing import Any

from app.adapters.entries import fill_entry_permissions
from app.errors import ApiError

_SETTINGS_BOOLS = ("silentLoading", "dependentSelectors", "expandTOC")
_SETTINGS_REQUIRED_NULL = ("autoupdateInterval", "maxConcurrentRequests")

_SETTINGS_KEYS = {
    "autoupdateInterval",
    "maxConcurrentRequests",
    "loadPriority",
    "silentLoading",
    "dependentSelectors",
    "globalParams",
    "signedGlobalParams",
    "hideTabs",
    "hideDashTitle",
    "expandTOC",
    "backgroundSettings",
    "widgetsSettings",
    "loadOnlyVisibleCharts",
    "margins",
    "enableAssistant",
    "aiChatHistoryEnabled",
}

_TAB_KEYS = (
    "id",
    "title",
    "hidden",
    "items",
    "layout",
    "connections",
    "aliases",
    "globalItems",
    "settings",
)

_TAB_SETTINGS_KEYS = ("fixedHeaderCollapsedDefault", "isGoldenset")

_ITEM_KEYS = (
    "id",
    "namespace",
    "orderId",
    "defaultOrderId",
    "type",
    "data",
    "defaults",
)

_GROUP_CONTROL_BOOLS = (
    "autoHeight",
    "buttonApply",
    "buttonReset",
    "showGroupName",
)
_GROUP_IMPACT_CLOUD = frozenset({"allTabs", "currentTab", "selectedTabs"})

_DATA_KEYS = (
    "counter",
    "salt",
    "schemeVersion",
    "tabs",
    "settings",
    "supportDescription",
    "accessDescription",
    "description",
)


def _adapt_settings(raw: Any) -> dict:
    settings = dict(raw) if isinstance(raw, dict) else {}
    settings = {key: settings[key] for key in _SETTINGS_KEYS if key in settings}
    for key in _SETTINGS_BOOLS:
        if key not in settings:
            settings[key] = False
    for key in _SETTINGS_REQUIRED_NULL:
        if key not in settings:
            settings[key] = None
    return settings


def _adapt_aliases(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    if "default" not in raw:
        return {}
    default = raw["default"]
    if default is None:
        return {}
    if not isinstance(default, list):
        return {}
    if not all(
        isinstance(group, list)
        and all(isinstance(name, str) and name for name in group)
        for group in default
    ):
        return {}
    return {"default": default}


def _adapt_group_control_data(raw: Any) -> dict:
    data = dict(raw) if isinstance(raw, dict) else {}
    for key in _GROUP_CONTROL_BOOLS:
        if key not in data:
            data[key] = False
    if data.get("impactType") not in _GROUP_IMPACT_CLOUD:
        data.pop("impactType", None)
    if "group" not in data:
        data["group"] = []
    return data


def _adapt_item(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw
    item = {key: raw[key] for key in _ITEM_KEYS if key in raw}
    if item.get("type") == "group_control":
        item["data"] = _adapt_group_control_data(item.get("data"))
    return item


def _adapt_tab_settings(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw
    return {key: raw[key] for key in _TAB_SETTINGS_KEYS if key in raw}


def _adapt_tab(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw
    tab = {key: raw[key] for key in _TAB_KEYS if key in raw}
    if "connections" not in tab:
        tab["connections"] = []
    tab["aliases"] = _adapt_aliases(tab.get("aliases"))
    items = tab.get("items")
    if isinstance(items, list):
        tab["items"] = [_adapt_item(item) for item in items]
    global_items = tab.get("globalItems")
    if isinstance(global_items, list):
        tab["globalItems"] = [_adapt_item(item) for item in global_items]
    if "settings" in tab:
        tab["settings"] = _adapt_tab_settings(tab["settings"])
    return tab


def _adapt_data(raw: Any) -> dict:
    src = dict(raw) if isinstance(raw, dict) else {}
    data = {key: src[key] for key in _DATA_KEYS if key in src}
    data["settings"] = _adapt_settings(data.get("settings"))
    tabs = data.get("tabs")
    if isinstance(tabs, list):
        data["tabs"] = [_adapt_tab(tab) for tab in tabs]
    if data.get("schemeVersion") != 8:
        data["schemeVersion"] = 8
    return data


def entry_to_dashboard_v1(raw: dict) -> dict:
    if not isinstance(raw, dict) or "entryId" not in raw:
        raise ApiError(500, "INTERNAL", "US entry missing entryId")
    entry_type = raw.get("type")
    if entry_type in (None, "dash"):
        entry_type = ""
    version = raw.get("version")
    if version is None:
        version = 1
    return {
        "annotation": raw.get("annotation"),
        "createdAt": raw.get("createdAt") or "",
        "createdBy": raw.get("createdBy") or "",
        "data": _adapt_data(raw.get("data")),
        "entryId": raw["entryId"],
        "hidden": bool(raw["hidden"]) if "hidden" in raw else False,
        "key": raw.get("key"),
        "links": raw.get("links"),
        "meta": raw.get("meta"),
        "public": bool(raw["public"]) if "public" in raw else False,
        "publishedId": raw.get("publishedId"),
        "revId": raw.get("revId") or raw.get("savedId") or "",
        "savedId": raw.get("savedId") or raw.get("revId") or "",
        "scope": raw.get("scope") or "dash",
        "tenantId": raw.get("tenantId") or "common",
        "type": entry_type,
        "updatedAt": raw.get("updatedAt") or raw.get("createdAt") or "",
        "updatedBy": raw.get("updatedBy") or raw.get("createdBy") or "",
        "version": version,
        "workbookId": raw.get("workbookId"),
    }


def dashboard_result(raw: dict) -> dict:
    result: dict[str, Any] = {"entry": entry_to_dashboard_v1(raw)}
    if raw.get("permissions") is not None:
        result["permissions"] = fill_entry_permissions(raw.get("permissions"))
    if "isFavorite" in raw:
        result["isFavorite"] = bool(raw["isFavorite"])
    return result
