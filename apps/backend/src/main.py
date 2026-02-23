from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.container import Container
from src.infrastructure.db.base import Base
from src.infrastructure.db.engine import engine
from src.infrastructure.db.models import KnowledgeBaseModel, TenantModel  # noqa: F401
from src.interfaces.api.auth_router import router as auth_router
from src.interfaces.api.health_router import router as health_router
from src.interfaces.api.knowledge_base_router import router as kb_router
from src.interfaces.api.tenant_router import router as tenant_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


def create_app() -> FastAPI:
    container = Container()

    application = FastAPI(
        title="Agentic RAG Customer Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.container = container  # type: ignore[attr-defined]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(tenant_router)
    application.include_router(kb_router)

    return application


app = create_app()
