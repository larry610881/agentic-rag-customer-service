from __future__ import annotations

import asyncio
import sys
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

# Early startup banner — printed before any heavy imports so Cloud Run
# logs always contain at least this line even when the process crashes.
print("[startup] importing modules ...", flush=True)

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from src.config import settings
    from src.container import Container
    from src.domain.shared.exceptions import DomainException, EntityNotFoundError
    from src.infrastructure.db.engine import engine
    from src.infrastructure.db.models import (  # noqa: F401
        BotKnowledgeBaseModel,
        BotModel,
        BuiltInToolModel,
        ChunkModel,
        ConversationModel,
        DocumentModel,
        ErrorEventModel,
        ErrorNotificationLogModel,
        FeedbackModel,
        KnowledgeBaseModel,
        LogRetentionPolicyModel,
        McpServerModel,
        MessageModel,
        NotificationChannelModel,
        ProcessingTaskModel,
        ProviderSettingModel,
        RAGEvalModel,
        RateLimitConfigModel,
        RequestLogModel,
        SystemPromptConfigModel,
        TenantModel,
        UsageRecordModel,
        UserModel,
    )
    from src.infrastructure.logging import get_logger, setup_logging

    print("[startup] imports OK", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(1)

logger = get_logger(__name__)


async def _log_cleanup_loop(container: object) -> None:
    """Background loop: check log retention policy and execute cleanup if due."""
    while True:
        await asyncio.sleep(3600)  # check every hour
        try:
            repo = container.log_retention_policy_repository()  # type: ignore[attr-defined]
            policy = await repo.get()
            if not policy or not policy.enabled:
                continue
            now = datetime.now(timezone.utc)
            if policy.last_cleanup_at:
                next_run = policy.last_cleanup_at + timedelta(
                    hours=policy.cleanup_interval_hours
                )
                if now < next_run:
                    continue
                if now.hour != policy.cleanup_hour:
                    continue
            uc = container.execute_log_cleanup_use_case()  # type: ignore[attr-defined]
            deleted = await uc.execute()
            logger.info("log_cleanup.success", deleted_count=deleted)
        except Exception:
            logger.warning("log_cleanup.failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging(
        log_level=settings.effective_log_level,
        app_env=settings.app_env,
    )
    logger.info(
        "app.startup",
        app_env=settings.app_env,
        log_level=settings.effective_log_level,
        enabled_modules=settings.enabled_modules,
    )

    # Seed built-in tools (idempotent — preserves admin-set scope/tenant_ids)
    try:
        from copy import deepcopy

        from src.domain.agent.built_in_tool import BUILT_IN_TOOL_DEFAULTS

        container = app.container  # type: ignore[attr-defined]
        session_factory = container.trace_session_factory()
        async with session_factory() as session:
            from src.infrastructure.db.repositories.built_in_tool_repository import (
                SQLAlchemyBuiltInToolRepository,
            )

            repo = SQLAlchemyBuiltInToolRepository(session=session)
            await repo.seed_defaults(deepcopy(BUILT_IN_TOOL_DEFAULTS))
        logger.info("built_in_tool.seed.success", count=len(BUILT_IN_TOOL_DEFAULTS))
    except Exception:
        logger.warning("built_in_tool.seed.failed", exc_info=True)

    # S-Pricing.1: 啟動時 load DB pricing 到記憶體 cache
    # 失敗不擋啟動 — RecordUsageUseCase 會 fallback 到 DEFAULT_MODELS
    try:
        container = app.container  # type: ignore[attr-defined]
        pricing_cache = container.pricing_cache()
        await pricing_cache.refresh()
    except Exception:
        logger.warning("pricing_cache.startup_refresh_failed", exc_info=True)

    # Start background log cleanup
    cleanup_task = asyncio.create_task(
        _log_cleanup_loop(app.container)  # type: ignore[attr-defined]
    )

    yield

    # Stop background cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    logger.info("app.shutdown")
    # Close Redis connection
    try:
        container = app.container  # type: ignore[attr-defined]
        redis_client = container.redis_client()
        await redis_client.aclose()
    except Exception:
        pass
    await engine.dispose()


def create_app(*, skip_rate_limit: bool = False) -> FastAPI:
    container = Container()

    # E2E mode: override llm_service so agent_service also uses FakeLLM
    if container.config().e2e_mode:
        container.llm_service.override(container._static_llm_service)

    application = FastAPI(
        title="Agentic RAG Customer Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.container = container  # type: ignore[attr-defined]

    from src.infrastructure.db.session_middleware import SessionCleanupMiddleware
    from src.interfaces.api.middleware import (
        RequestIDMiddleware,
        RequestTimeoutMiddleware,
    )

    # Middleware order: last added = outermost in ASGI chain.
    # Execution: SessionCleanup → RequestID → Timeout → CORS → RateLimit → Route
    #
    # RequestID must run before RateLimit so that:
    # 1. request_id is set before any trace logging
    # 2. init_trace() buffer is ready to capture rate limit steps

    # Rate Limit Middleware (innermost, runs just before route handlers)
    if not skip_rate_limit and settings.rate_limit_enabled:
        from src.infrastructure.ratelimit.config_loader import RateLimitConfigLoader
        from src.infrastructure.ratelimit.redis_rate_limiter import RedisRateLimiter
        from src.interfaces.api.rate_limit_middleware import RateLimitMiddleware

        rate_limiter = RedisRateLimiter(redis_client=container.redis_client())
        config_loader = RateLimitConfigLoader(
            rate_limit_config_repo_factory=container.rate_limit_config_repository,
            redis_client=container.redis_client(),
            cache_ttl=settings.rate_limit_config_cache_ttl,
        )
        application.add_middleware(
            RateLimitMiddleware,
            rate_limiter=rate_limiter,
            config_loader=config_loader,
            jwt_secret_key=settings.jwt_secret_key,
            jwt_algorithm=settings.jwt_algorithm,
            global_rpm=settings.rate_limit_global_rpm,
        )

    # Request Timeout (between CORS and RequestID)
    application.add_middleware(
        RequestTimeoutMiddleware,
        timeout=settings.request_timeout,
        stream_timeout=settings.stream_request_timeout,
    )

    from src.interfaces.api.middleware import CORSMiddlewareWithExclusions

    cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    print(f"[startup] CORS origins: {cors_origins!r}", flush=True)
    application.add_middleware(
        CORSMiddlewareWithExclusions,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # RequestID + trace init/flush (runs before CORS & RateLimit)
    application.add_middleware(RequestIDMiddleware)

    # SessionCleanupMiddleware MUST be the last add_middleware call.
    # Last added = outermost in ASGI chain = executes after all inner
    # middleware finish. This guarantees every AsyncSession created
    # during the request (including by RateLimitMiddleware) is closed.
    application.add_middleware(SessionCleanupMiddleware)

    @application.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(
        request: Request, exc: EntityNotFoundError
    ) -> JSONResponse:
        logger.warning("domain.entity_not_found", error=exc.message)
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @application.exception_handler(DomainException)
    async def domain_exception_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        logger.warning("domain.error", error=exc.message)
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        from src.infrastructure.logging.error_context import set_captured_error

        logger.exception("unhandled_error", error=str(exc))
        set_captured_error(f"{type(exc).__name__}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    modules = settings.enabled_modules_set

    # Health is always loaded
    from src.interfaces.api.health_router import router as health_router
    from src.interfaces.api.log_router import router as log_router

    application.include_router(health_router)
    application.include_router(log_router)

    # API module: tenant management, knowledge, bot, reports, etc.
    if "api" in modules:
        from src.interfaces.api.agent_router import router as agent_router
        from src.interfaces.api.auth_router import router as auth_router
        from src.interfaces.api.bot_router import router as bot_router
        from src.interfaces.api.conversation_router import router as conversation_router
        from src.interfaces.api.document_router import router as document_router
        from src.interfaces.api.knowledge_base_router import router as kb_router
        from src.interfaces.api.rag_router import router as rag_router
        from src.interfaces.api.task_router import router as task_router
        from src.interfaces.api.tenant_router import router as tenant_router
        from src.interfaces.api.usage_router import router as usage_router
        from src.interfaces.api.worker_router import router as worker_router

        application.include_router(auth_router)
        application.include_router(tenant_router)
        application.include_router(kb_router)
        application.include_router(document_router)
        application.include_router(task_router)
        application.include_router(rag_router)
        application.include_router(agent_router)
        application.include_router(conversation_router)
        application.include_router(usage_router)
        application.include_router(bot_router)
        application.include_router(worker_router)

        from src.interfaces.api.admin_router import router as admin_router
        from src.interfaces.api.feedback_router import router as feedback_router
        from src.interfaces.api.provider_setting_router import (
            router as provider_setting_router,
        )

        application.include_router(provider_setting_router)
        application.include_router(feedback_router)
        application.include_router(admin_router)

        # HARDCODE - 地端模型 A/B 測試路由，正式上線前移除
        from src.interfaces.api.ollama_router import router as ollama_router
        application.include_router(ollama_router)

        from src.interfaces.api.admin_tools_router import (
            router as admin_tools_router,
        )
        from src.interfaces.api.admin_bot_router import (
            router as admin_bot_router,
        )
        from src.interfaces.api.admin_knowledge_base_router import (
            router as admin_knowledge_base_router,
        )

        application.include_router(admin_tools_router)
        application.include_router(admin_bot_router)
        application.include_router(admin_knowledge_base_router)

        from src.interfaces.api.admin_pricing_router import (
            router as admin_pricing_router,
        )
        application.include_router(admin_pricing_router)

        from src.interfaces.api.plan_router import router as plan_router
        application.include_router(plan_router)

        from src.interfaces.api.mcp_router import router as mcp_router
        from src.interfaces.api.mcp_server_router import router as mcp_server_router
        from src.interfaces.api.system_prompt_router import (
            router as system_prompt_router,
        )

        application.include_router(mcp_router)
        application.include_router(mcp_server_router)
        application.include_router(system_prompt_router)

        from src.interfaces.api.observability_router import (
            router as observability_router,
        )

        application.include_router(observability_router)

        from src.interfaces.api.security_router import router as security_router

        application.include_router(security_router)

        from src.interfaces.api.error_event_router import (
            router as error_event_router,
        )
        from src.interfaces.api.notification_router import (
            router as notification_router,
        )

        application.include_router(error_event_router)
        application.include_router(notification_router)

        from src.interfaces.api.widget_router import router as widget_router

        application.include_router(widget_router)

        from src.interfaces.api.eval_dataset_router import (
            router as eval_dataset_router,
        )

        application.include_router(eval_dataset_router)

        from src.interfaces.api.prompt_optimizer_run_router import (
            router as prompt_optimizer_run_router,
        )

        application.include_router(prompt_optimizer_run_router)

    # Static files for widget.js
    import os

    from starlette.staticfiles import StaticFiles

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    if os.path.isdir(static_dir):
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Webhook module: LINE Bot
    if "webhook" in modules:
        from src.interfaces.api.line_webhook_router import router as line_webhook_router

        application.include_router(line_webhook_router)

    # WebSocket module: Web Chat (placeholder for E1.5)
    # if "websocket" in modules:
    #     from src.interfaces.ws.chat_websocket import ws_router
    #     application.include_router(ws_router)

    logger.info(
        "app.modules_loaded",
        modules=list(modules),
    )

    return application


try:
    app = create_app()
    print("[startup] app created OK — ready to serve", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(1)
