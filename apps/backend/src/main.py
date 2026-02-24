import sqlalchemy
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
    KnowledgeBaseModel,
    MessageModel,
    ProcessingTaskModel,
    TenantModel,
    TicketModel,
    UsageRecordModel,
)
from src.infrastructure.logging import get_logger, setup_logging
from src.interfaces.api.agent_router import router as agent_router
from src.interfaces.api.auth_router import router as auth_router
from src.interfaces.api.bot_router import router as bot_router
from src.interfaces.api.conversation_router import router as conversation_router
from src.interfaces.api.document_router import router as document_router
from src.interfaces.api.health_router import router as health_router
from src.interfaces.api.knowledge_base_router import router as kb_router
from src.interfaces.api.line_webhook_router import router as line_webhook_router
from src.interfaces.api.middleware import RequestIDMiddleware
from src.interfaces.api.rag_router import router as rag_router
from src.interfaces.api.task_router import router as task_router
from src.interfaces.api.tenant_router import router as tenant_router
from src.interfaces.api.usage_router import router as usage_router

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
    yield
    logger.info("app.shutdown")
    await engine.dispose()


def create_app() -> FastAPI:
    container = Container()

    application = FastAPI(
        title="Agentic RAG Customer Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.container = container  # type: ignore[attr-defined]

    application.add_middleware(RequestIDMiddleware)
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

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(tenant_router)
    application.include_router(kb_router)
    application.include_router(document_router)
    application.include_router(task_router)
    application.include_router(rag_router)
    application.include_router(agent_router)
    application.include_router(conversation_router)
    application.include_router(line_webhook_router)
    application.include_router(usage_router)
    application.include_router(bot_router)

    return application


app = create_app()
