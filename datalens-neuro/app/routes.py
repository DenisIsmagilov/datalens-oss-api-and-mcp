import hmac
import json
import pathlib

from fastapi import APIRouter, Depends, Header, Path, Request
from fastapi.responses import Response

from app.config import get_settings
from app.errors import NeuroError
from app.request_context import current_request_id
from app.schemas import ChatRequest, ChatResponse
from app.service import ChatService

router = APIRouter()

_LOADER_DISABLED = "/* datalens-neuro: ui disabled */\n"
_PANEL = pathlib.Path(__file__).resolve().parent / "ui" / "loader.js"


async def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = get_settings().neuro_api_token
    scheme, _, token = (authorization or "").partition(" ")
    if not expected or scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise NeuroError(401, "UNAUTHENTICATED", "Missing or invalid token")


def _service(request: Request) -> ChatService:
    return request.app.state.service


@router.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_token)])
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    if not get_settings().neuro_enabled:
        raise NeuroError(503, "NEURO_DISABLED", "Neuroanalyst is disabled")
    return await _service(request).chat(body, trace_id=current_request_id())


@router.get("/v1/conversations/{conversation_id}", dependencies=[Depends(require_token)])
async def conversation(
    request: Request, conversation_id: str = Path(pattern=r"^c_[0-9a-f]{20}$")
) -> dict:
    detail = await request.app.state.store.conversation_detail(conversation_id)
    if detail is None:
        raise NeuroError(404, "NOT_FOUND", "Conversation not found", {"conversationId": conversation_id})
    return detail


@router.get("/v1/status", dependencies=[Depends(require_token)])
async def status(request: Request) -> dict:
    settings = get_settings()
    packs = request.app.state.packs
    return {
        "enabled": settings.neuro_enabled,
        "uiEnabled": settings.neuro_ui_enabled,
        "defaultPack": settings.neuro_default_pack,
        "packs": [
            {"name": p.name, "title": p.title, "workbookIds": p.workbook_ids} for p in packs.packs.values()
        ],
        "packErrors": packs.errors,
        "model": settings.llm_model or None,
        "llmConfigured": _service(request).llm_configured,
    }


@router.get("/ui/loader.js")
async def loader() -> Response:
    settings = get_settings()
    if settings.neuro_enabled and settings.neuro_ui_enabled:
        body = _PANEL.read_text(encoding="utf-8").replace(
            "__NEURO_UI_TITLE_JSON__", json.dumps(settings.neuro_ui_title, ensure_ascii=False)
        )
    else:
        body = _LOADER_DISABLED
    return Response(body, media_type="application/javascript", headers={"Cache-Control": "no-store"})
