from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sqlalchemy
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.container import Container
from src.domain.shared.exceptions import DomainException, EntityNotFoundError
from src.infrastructure.db.base import Base
from src.infrastructure.db.engine import engine
from src.infrastructure.db.models import (  # noqa: F401
    BotKnowledgeBaseModel,
    BotModel,
    ChunkModel,
    ConversationModel,
    DocumentModel,
    FeedbackModel,
    KnowledgeBaseModel,
    MessageModel,
    ProcessingTaskModel,
    ProviderSettingModel,
    RateLimitConfigModel,
    TenantModel,
    UsageRecordModel,
    UserModel,
)
from src.infrastructure.logging import get_logger, setup_logging

logger = get_logger(__name__)


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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration: add columns if missing
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE bots ADD COLUMN IF NOT EXISTS "
                "enabled_tools JSON NOT NULL DEFAULT ('[]')"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE bots ADD COLUMN IF NOT EXISTS "
                "rag_top_k INTEGER NOT NULL DEFAULT 5"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE bots ADD COLUMN IF NOT EXISTS "
                "rag_score_threshold FLOAT NOT NULL DEFAULT 0.3"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS "
                "bot_id VARCHAR(36) DEFAULT NULL"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_tenant_bot "
                "ON conversations (tenant_id, bot_id)"
            )
        )
        # Document quality metrics columns
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                "avg_chunk_length INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                "min_chunk_length INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                "max_chunk_length INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                "quality_score FLOAT NOT NULL DEFAULT 0.0"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                "quality_issues TEXT NOT NULL DEFAULT ''"
            )
        )
        # One-time cleanup: remove orphan messages then unbound conversations
        await conn.execute(
            sqlalchemy.text(
                "DELETE FROM messages WHERE conversation_id IN "
                "(SELECT id FROM conversations WHERE bot_id IS NULL)"
            )
        )
        await conn.execute(
            sqlalchemy.text(
                "DELETE FROM conversations WHERE bot_id IS NULL"
            )
        )
    yield
    logger.info("app.shutdown")
    # Close Redis connection
    try:
        container = app.container  # type: ignore[attr-defined]
        redis_client = container.redis_client()
        await redis_client.aclose()
    except Exception:
        pass
    await engine.dispose()


def create_app() -> FastAPI:
    container = Container()

    application = FastAPI(
        title="Agentic RAG Customer Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.container = container  # type: ignore[attr-defined]

    from src.interfaces.api.middleware import RequestIDMiddleware

    application.add_middleware(RequestIDMiddleware)

    # Rate Limit Middleware (runs after CORS, before route handlers)
    from src.infrastructure.ratelimit.config_loader import RateLimitConfigLoader
    from src.infrastructure.ratelimit.redis_rate_limiter import RedisRateLimiter
    from src.interfaces.api.rate_limit_middleware import RateLimitMiddleware

    rate_limiter = RedisRateLimiter(redis_client=container.redis_client())
    config_loader = RateLimitConfigLoader(
        rate_limit_config_repository=container.rate_limit_config_repository(),
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

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        logger.exception("unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    modules = settings.enabled_modules_set

    # Health is always loaded
    from src.interfaces.api.health_router import router as health_router

    application.include_router(health_router)

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

        from src.interfaces.api.admin_router import router as admin_router
        from src.interfaces.api.feedback_router import router as feedback_router
        from src.interfaces.api.provider_setting_router import (
            router as provider_setting_router,
        )

        application.include_router(provider_setting_router)
        application.include_router(feedback_router)
        application.include_router(admin_router)

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


app = create_app()
