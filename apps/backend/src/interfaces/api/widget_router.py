"""Widget 公開 Chat API — 外部網站嵌入式聊天（Issue #67 P4：短效 widget 票）

流程：
1. ``GET /{code}/config``：Origin 必須在 bot 白名單（白名單為空一律拒）→ 回設定 +
   ``widget_token``（type=widget_access，綁 bot / Origin / visitor，15 分鐘）+ 伺服器
   簽發的 ``visitor_id``。
2. chat/stream、feedback、error、documents/view 都必須帶票（Authorization: Bearer
   或 ``?wt=`` query，後者給新分頁開啟文件用）；票的 bot / Origin 與請求不符即拒。
3. 訪客身分取自票，不再信任 X-Visitor-Id header。
"""

import json
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.abuse.abuse_control_service import AbuseControlService
from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackCommand,
    SubmitFeedbackUseCase,
)
from src.application.knowledge.view_document_use_case import (
    ViewDocumentUseCase,
)
from src.application.observability.error_event_use_cases import (
    ReportErrorCommand,
    ReportErrorUseCase,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.application.widget.identity_use_cases import VerifyWidgetIdentityUseCase
from src.container import Container
from src.domain.abuse.policy import AbuseSubject, SubjectKind
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.knowledge.repository import DocumentRepository
from src.infrastructure.auth.jwt_service import WIDGET_TOKEN_TYPE, JWTService
from src.infrastructure.auth.visitor_id_signer import VisitorIdSigner
from src.interfaces.api.client_ip import client_ip_of
from src.interfaces.api.streaming_errors import classify_streaming_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widget", tags=["widget"])

_ALLOW_HEADERS = "Content-Type, Authorization, X-Visitor-Id"


class WidgetChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    metadata: dict | None = None  # 預留


class WidgetFeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    rating: str  # "thumbs_up" | "thumbs_down"
    comment: str | None = None
    tags: list[str] = []


class WidgetErrorRequest(BaseModel):
    error_type: str
    message: str
    stack_trace: str | None = None
    path: str | None = None
    user_agent: str | None = None


class WidgetConfigResponse(BaseModel):
    name: str
    description: str
    keep_history: bool
    show_sources: bool = True
    welcome_message: str = ""
    placeholder_text: str = ""
    greeting_messages: list[str] = []
    greeting_animation: str = "fade"
    fab_icon_url: str = ""
    # Issue #67 P4
    widget_token: str = ""
    token_expires_in: int = 0
    visitor_id: str = ""


@dataclass
class WidgetPrincipal:
    bot: Bot
    origin: str
    visitor_id: str | None
    end_user_id: str | None = None  # P7b：identify() 通過後的宿主使用者 id

    @property
    def subject(self) -> tuple[str, str]:
        if self.end_user_id:
            return "end_user", self.end_user_id
        return "visitor", self.visitor_id or "anon"


def request_origin(request: Request) -> str | None:
    """Origin header；沒有（同源 GET / 新分頁開啟）則退回 Referer 的 origin。"""
    origin = request.headers.get("origin")
    if origin:
        return origin
    referer = request.headers.get("referer")
    if referer:
        parts = urlsplit(referer)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}"
    return None


async def validate_widget_bot(
    short_code: str,
    origin: str | None,
    bot_repo: BotRepository,
) -> Bot:
    """bot 存在、啟用、開放 widget、Origin 在白名單（白名單為空一律拒）。"""
    bot = await bot_repo.find_by_short_code(short_code)
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )
    if not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bot is not active",
        )
    if not bot.widget_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Widget is not enabled for this bot",
        )
    if not bot.widget_allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Widget origin allowlist is empty",
        )
    if not origin or origin not in bot.widget_allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        )
    return bot


def _bearer_or_query_token(request: Request, wt: str | None) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return wt or None


@inject
async def get_widget_principal(
    short_code: str,
    request: Request,
    wt: str | None = Query(default=None),
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
    abuse: AbuseControlService = Depends(Provide[Container.abuse_control_service]),
) -> WidgetPrincipal:
    """驗 widget 票：type、bot、Origin 三者都要對得上。"""
    token = _bearer_or_query_token(request, wt)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget token required"
        )
    try:
        payload = jwt_service.decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid widget token"
        ) from None
    if payload.get("type") != WIDGET_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid widget token"
        )
    token_origin = payload.get("origin") or ""
    bot = await validate_widget_bot(short_code, token_origin, bot_repo)
    if payload.get("sub") != bot.id.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Widget token does not match bot",
        )
    origin = request_origin(request)
    if origin is not None and origin != token_origin:
        # Issue #68 P7：票的 Origin 與請求不符 → 記一筆異常訊號（fail-open）
        visitor = payload.get("visitor_id")
        if visitor:
            await abuse.record(
                bot.tenant_id, AbuseSubject(SubjectKind.VISITOR, visitor),
                origin_mismatch=True, channel="widget",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed"
        )
    return WidgetPrincipal(
        bot=bot, origin=token_origin, visitor_id=payload.get("visitor_id"),
        end_user_id=payload.get("end_user_id"),
    )


def _widget_should_forward(
    event: dict, keep_history: bool, captured: dict
) -> bool:
    """決定 widget SSE 事件是否下發匿名前端，並側錄歸因欄位到 captured。

    - usage / config_version：內部事件，捕獲後不下發（H7 config_version；H8 歸因）。
    - guard_blocked：含命中規則原文（rule_matched，需 system_admin 才可正規讀取）與
      replacement，匿名通路不得外洩，否則可逐條探針枚舉整份防護規則（H7）。
    - message_id：捕獲供版本成效歸因（H8），仍下發以與 web 對齊。
    - conversation_id：keep_history 關閉時不下發。
    """
    etype = event.get("type")
    if etype == "usage":
        captured["usage"] = event
        return False
    if etype == "config_version":
        captured["config_version_id"] = event.get("config_version_id")
        return False
    if etype == "config_hash":
        captured["config_hash"] = event.get("config_hash")
        return False
    if etype == "guard_blocked":
        return False
    if etype == "message_id":
        captured["message_id"] = event.get("message_id")
        return True
    if etype == "conversation_id" and not keep_history:
        return False
    return True


def _set_cors_headers(response, origin: str | None, bot: Bot) -> None:
    """Set dynamic CORS headers based on bot's allowed origins."""
    if origin and origin in bot.widget_allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = _ALLOW_HEADERS
        response.headers["Vary"] = "Origin"


@router.options("/{short_code}/chat/stream")
@router.options("/{short_code}/config")
@router.options("/{short_code}/feedback")
@router.options("/{short_code}/error")
@router.options("/{short_code}/identify")
@inject
async def widget_cors_preflight(
    short_code: str,
    request: Request,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
) -> Response:
    """CORS preflight — dynamic allowed origin."""
    origin = request.headers.get("origin")
    bot = await bot_repo.find_by_short_code(short_code)

    resp = Response(status_code=204)
    if bot and bot.widget_enabled and origin and origin in bot.widget_allowed_origins:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = _ALLOW_HEADERS
        resp.headers["Access-Control-Max-Age"] = "3600"
        resp.headers["Vary"] = "Origin"
    return resp


@router.get("/{short_code}/config", response_model=WidgetConfigResponse)
@inject
async def widget_config(
    short_code: str,
    request: Request,
    response: Response,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
    signer: VisitorIdSigner = Depends(Provide[Container.visitor_id_signer]),
) -> WidgetConfigResponse:
    """Public entry: Origin 白名單驗證後回設定 + 短效票 + 簽發訪客身分。"""
    origin = request_origin(request)
    bot = await validate_widget_bot(short_code, origin, bot_repo)
    assert origin is not None  # validate_widget_bot 已保證

    presented = request.headers.get("x-visitor-id")
    raw_visitor = signer.verify(presented)
    if raw_visitor is None:
        signed_visitor = signer.issue()
        raw_visitor = signer.verify(signed_visitor) or ""
    else:
        signed_visitor = presented or ""

    token, expires_in = jwt_service.create_widget_token(
        bot_id=bot.id.value,
        tenant_id=bot.tenant_id,
        origin=origin,
        visitor_id=raw_visitor,
    )

    _set_cors_headers(response, origin, bot)

    return WidgetConfigResponse(
        name=bot.name,
        description=bot.description,
        keep_history=bot.widget_keep_history,
        show_sources=bot.show_sources,
        welcome_message=bot.widget_welcome_message,
        placeholder_text=bot.widget_placeholder_text,
        greeting_messages=bot.widget_greeting_messages,
        greeting_animation=bot.widget_greeting_animation,
        fab_icon_url=bot.fab_icon_url,
        widget_token=token,
        token_expires_in=expires_in,
        visitor_id=signed_visitor,
    )


@router.post("/{short_code}/chat/stream")
@inject
async def widget_chat_stream(
    short_code: str,
    body: WidgetChatRequest,
    request: Request,
    principal: WidgetPrincipal = Depends(get_widget_principal),
    use_case: SendMessageUseCase = Depends(
        Provide[Container.send_message_use_case]
    ),
    record_usage: RecordUsageUseCase = Depends(
        Provide[Container.record_usage_use_case]
    ),
) -> StreamingResponse:
    """SSE streaming chat（需 widget 票）。"""
    bot = principal.bot
    command = SendMessageCommand(
        tenant_id=bot.tenant_id,
        bot_id=bot.id.value,
        message=body.message,
        conversation_id=body.conversation_id if bot.widget_keep_history else None,
        # 取自票，不信任 header；identify() 通過後改用宿主 user id（記憶 / 紀錄綁定）
        visitor_id=principal.end_user_id or principal.visitor_id,
        # L6：widget 端點固定通路標記——trace source 不再 fallback 成 "web"
        identity_source="widget",
        subject_kind=principal.subject[0],
        subject_id=principal.subject[1],
        client_ip=client_ip_of(request),
    )
    # Issue #68 P7：串流前先問異常等級（L3+ → 429）
    await use_case.abuse_preflight(command)

    async def event_generator():
        captured: dict = {}
        try:
            async for event in use_case.execute_stream(command):
                if _widget_should_forward(event, bot.widget_keep_history, captured):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("widget.chat.stream.error")
            error_msg = classify_streaming_error(exc)
            # L5：與 agent_router 對齊（channel parity）——標記+持久化 failed trace
            from src.interfaces.api._streaming_failure import (
                persist_failed_stream_trace,
            )

            failed_trace_id = await persist_failed_stream_trace(
                use_case,
                conversation_id=command.conversation_id,
                source="widget",
                error_msg=error_msg,
            )
            error_payload = {"type": "error", "message": error_msg}
            done_payload: dict = {"type": "done"}
            if failed_trace_id:
                done_payload["trace_id"] = failed_trace_id
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

        # Record token usage after stream completes
        usage_data = captured.get("usage")
        if usage_data:
            from src.infrastructure.langgraph.usage import (
                extract_usage_from_accumulated,
            )

            usage = extract_usage_from_accumulated(usage_data)
            if usage is not None:
                try:
                    await record_usage.execute(
                        tenant_id=bot.tenant_id,
                        request_type="chat_widget",
                        usage=usage,
                        bot_id=bot.id.value,
                        message_id=captured.get("message_id"),  # H8
                        config_version_id=captured.get("config_version_id"),  # H8
                        config_hash=captured.get("config_hash"),
                    )
                except Exception:
                    logger.exception("widget.chat.stream.record_usage_error")

    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
    _set_cors_headers(response, principal.origin, bot)
    return response


class WidgetIdentifyRequest(BaseModel):
    user_id: str
    exp: int
    hash: str
    name: str | None = None
    email: str | None = None


class WidgetIdentifyResponse(BaseModel):
    identified: bool
    widget_token: str = ""
    token_expires_in: int = 0
    reason: str = ""


@router.post("/{short_code}/identify", response_model=WidgetIdentifyResponse)
@inject
async def widget_identify(
    short_code: str,
    body: WidgetIdentifyRequest,
    response: Response,
    principal: WidgetPrincipal = Depends(get_widget_principal),
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
    use_case: VerifyWidgetIdentityUseCase = Depends(
        Provide[Container.verify_widget_identity_use_case]
    ),
) -> WidgetIdentifyResponse:
    """宿主身分綁定（P7b）：hash = HMAC-SHA256(secret, f"{user_id}.{exp}")。

    通過 → 換一張帶 end_user_id 的 widget 票；失敗 → 預設維持匿名（計分），
    租戶開「強制驗證」則 403。
    """
    bot = principal.bot
    verdict = await use_case.execute(
        tenant_id=bot.tenant_id, visitor_id=principal.visitor_id,
        user_id=body.user_id.strip()[:128], exp=body.exp, presented_hash=body.hash,
    )
    _set_cors_headers(response, principal.origin, bot)
    if not verdict.verified:
        if verdict.enforce and verdict.reason == "invalid":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="identity_required"
            )
        return WidgetIdentifyResponse(identified=False, reason=verdict.reason)
    token, expires_in = jwt_service.create_widget_token(
        bot_id=bot.id.value, tenant_id=bot.tenant_id, origin=principal.origin,
        visitor_id=principal.visitor_id or "", end_user_id=body.user_id.strip()[:128],
    )
    return WidgetIdentifyResponse(
        identified=True, widget_token=token, token_expires_in=expires_in
    )


@router.post("/{short_code}/feedback", status_code=201)
@inject
async def widget_feedback(
    short_code: str,
    body: WidgetFeedbackRequest,
    response: Response,
    principal: WidgetPrincipal = Depends(get_widget_principal),
    use_case: SubmitFeedbackUseCase = Depends(
        Provide[Container.submit_feedback_use_case]
    ),
) -> dict:
    """Submit feedback from widget（需 widget 票）。"""
    bot = principal.bot
    command = SubmitFeedbackCommand(
        tenant_id=bot.tenant_id,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        channel="widget",
        rating=body.rating,
        comment=body.comment,
        tags=body.tags,
    )
    await use_case.execute(command)

    _set_cors_headers(response, principal.origin, bot)
    return {"success": True}


@router.post("/{short_code}/error", status_code=201)
@inject
async def widget_error_report(
    short_code: str,
    body: WidgetErrorRequest,
    response: Response,
    principal: WidgetPrincipal = Depends(get_widget_principal),
    use_case: ReportErrorUseCase = Depends(
        Provide[Container.report_error_use_case]
    ),
) -> dict:
    """Report errors from widget（需 widget 票）。"""
    event = await use_case.execute(
        ReportErrorCommand(
            source="widget",
            error_type=body.error_type,
            message=body.message,
            stack_trace=body.stack_trace,
            path=body.path,
            user_agent=body.user_agent,
        )
    )

    _set_cors_headers(response, principal.origin, principal.bot)
    return {"id": event.id, "fingerprint": event.fingerprint}


@router.get("/{short_code}/documents/{doc_id}/view")
@inject
async def widget_view_document(
    short_code: str,
    doc_id: str,
    principal: WidgetPrincipal = Depends(get_widget_principal),
    doc_repo: DocumentRepository = Depends(
        Provide[Container.document_repository]
    ),
    use_case: ViewDocumentUseCase = Depends(
        Provide[Container.view_document_use_case]
    ),
) -> Response:
    """View original document file（需 widget 票；新分頁開啟時以 ?wt= 帶票）。"""
    bot = principal.bot
    if not bot.show_sources:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source viewing is disabled for this bot",
        )

    # Verify document belongs to one of this bot's knowledge bases
    doc = await doc_repo.find_by_id(doc_id)
    if doc is None or doc.kb_id not in bot.knowledge_base_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    result = await use_case.execute(doc_id)

    resp = Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{result.filename}"'
        },
    )
    _set_cors_headers(resp, principal.origin, bot)
    return resp
