from fastapi import APIRouter, Request
from pydantic import ValidationError

from app.config import get_settings
from app.errors import NeuroError
from app.request_context import current_request_id
from app.schemas import ChatContext, ChatRequest, ChatUser
from app.ui_auth import access_token_from_cookie, verify_access_token

router = APIRouter()


def _page_context(raw) -> ChatContext | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise NeuroError(400, "INVALID_ARGUMENT", "context is invalid")
    try:
        context = ChatContext.model_validate(raw)
    except ValidationError:
        raise NeuroError(400, "INVALID_ARGUMENT", "context is invalid") from None
    if not context.dashboardId and not context.chartId and not context.tabId and not context.params:
        return None
    return context


def _formula_context(raw) -> tuple[str | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        raise NeuroError(400, "INVALID_ARGUMENT", "context is invalid")
    chart_id = raw.get("chartId")
    chart_kind = raw.get("chartKind")
    if chart_id is not None and not isinstance(chart_id, str):
        raise NeuroError(400, "INVALID_ARGUMENT", "context is invalid")
    if chart_kind is not None and not isinstance(chart_kind, str):
        raise NeuroError(400, "INVALID_ARGUMENT", "context is invalid")
    return chart_id, chart_kind


def _thread_messages(detail: dict) -> list[dict]:
    messages = []
    for message in detail["messages"]:
        item = {"role": message["role"], "content": message["content"]}
        if message["role"] == "assistant":
            item["sources"] = message["sources"]
            item["steps"] = message["steps"]
        messages.append(item)
    return messages


def begin(request: Request):
    settings = get_settings()
    if not settings.neuro_ui_enabled:
        raise NeuroError(404, "NOT_FOUND", "Not Found")
    if not settings.neuro_enabled:
        return None
    origin = request.headers.get("origin")
    if origin not in settings.ui_origins:
        raise NeuroError(403, "FORBIDDEN", "Origin is not allowed")
    token = access_token_from_cookie(request.headers.get("cookie"))
    if token is None:
        raise NeuroError(401, "UNAUTHENTICATED", "Missing or invalid token")
    user = verify_access_token(token, settings.auth_token_public_key)
    if not set(user.roles) & settings.ui_roles:
        raise NeuroError(403, "FORBIDDEN", "Role is not allowed")
    return user


@router.get("/v1/ui/session")
async def session(request: Request) -> dict:
    user = begin(request)
    if user is None:
        return {"enabled": False}
    return {"enabled": True, "userId": user.user_id, "roles": list(user.roles)}


@router.get("/v1/ui/thread")
async def thread(request: Request) -> dict:
    user = begin(request)
    if user is None:
        return {"enabled": False}
    settings = get_settings()
    conversation_id = await request.app.state.store.current_thread(
        user.user_id, settings.neuro_ui_conversation_idle_hours
    )
    if conversation_id is None:
        return {"conversationId": None, "messages": []}
    detail = await request.app.state.store.conversation_detail(conversation_id)
    return {"conversationId": conversation_id, "messages": _thread_messages(detail)}


@router.post("/v1/ui/chat")
async def chat(request: Request) -> dict:
    user = begin(request)
    if user is None:
        raise NeuroError(503, "NEURO_DISABLED", "Neuroanalyst is disabled")
    body = await request.json()
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        raise NeuroError(400, "INVALID_ARGUMENT", "message is required")
    context = _page_context(body.get("context") if isinstance(body, dict) else None)
    settings = get_settings()
    store = request.app.state.store
    conversation_id = await store.current_thread(user.user_id, settings.neuro_ui_conversation_idle_hours)
    result = await request.app.state.service.chat(
        ChatRequest(
            message=message.strip(),
            conversationId=conversation_id,
            context=context,
            user=ChatUser(externalId=f"dl:{user.user_id}"),
        ),
        trace_id=current_request_id(),
    )
    await store.bind_thread(user.user_id, result.conversationId)
    return result.model_dump()


@router.post("/v1/ui/new")
async def new_thread(request: Request) -> dict:
    user = begin(request)
    if user is None:
        raise NeuroError(503, "NEURO_DISABLED", "Neuroanalyst is disabled")
    await request.app.state.store.clear_thread(user.user_id)
    return {"ok": True}


@router.get("/v1/ui/formula/thread")
async def formula_thread(request: Request) -> dict:
    user = begin(request)
    if user is None:
        return {"enabled": False}
    settings = get_settings()
    conversation_id = await request.app.state.store.current_formula_thread(
        user.user_id, settings.neuro_ui_conversation_idle_hours
    )
    if conversation_id is None:
        return {"conversationId": None, "messages": []}
    detail = await request.app.state.store.conversation_detail(conversation_id)
    return {"conversationId": conversation_id, "messages": _thread_messages(detail)}


@router.post("/v1/ui/formula")
async def formula(request: Request) -> dict:
    user = begin(request)
    if user is None:
        raise NeuroError(503, "NEURO_DISABLED", "Neuroanalyst is disabled")
    body = await request.json()
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        raise NeuroError(400, "INVALID_ARGUMENT", "message is required")
    chart_id, chart_kind = _formula_context(body.get("context") if isinstance(body, dict) else None)
    result = await request.app.state.formula.turn(
        message.strip(),
        chart_id,
        chart_kind,
        user.user_id,
        current_request_id(),
    )
    return result.model_dump()


@router.post("/v1/ui/formula/new")
async def new_formula_thread(request: Request) -> dict:
    user = begin(request)
    if user is None:
        raise NeuroError(503, "NEURO_DISABLED", "Neuroanalyst is disabled")
    await request.app.state.store.clear_formula_thread(user.user_id)
    return {"ok": True}
