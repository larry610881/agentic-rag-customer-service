"""E2E Test Fixtures — multi-step user journeys over real DB.

Reuses integration conftest's DB/app infrastructure. Each journey test
exercises multiple API endpoints in sequence, simulating a complete user flow.
"""

import asyncio
import uuid

import pytest
from dependency_injector import providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from unittest.mock import AsyncMock

from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.db.base import Base

# Ensure all ORM models are registered
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

ADMIN_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag"
TEST_DB_NAME = "agentic_rag_e2e"
TEST_DB_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{TEST_DB_NAME}"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _terminate_connections():
    admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        from sqlalchemy import text
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                f"WHERE datname = '{TEST_DB_NAME}' "
                "AND pid <> pg_backend_pid()"
            )
        )
        for _ in range(50):
            result = await conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    f"WHERE datname = '{TEST_DB_NAME}'"
                )
            )
            if result.scalar() == 0:
                break
            await asyncio.sleep(0.1)
    await admin.dispose()


async def _force_drop_db():
    await _terminate_connections()
    admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        from sqlalchemy import text
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin.dispose()


@pytest.fixture(scope="session")
def _test_db():
    async def _setup():
        await _force_drop_db()
        admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        await admin.dispose()
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    _run(_setup())
    yield
    _run(_force_drop_db())


@pytest.fixture(autouse=True)
def _clean_db(_test_db):
    async def _reset():
        await _terminate_connections()
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    _run(_reset())


@pytest.fixture
def test_engine(_test_db):
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield engine
    _run(engine.dispose())


@pytest.fixture
def app(test_engine):
    from src.main import create_app

    application = create_app(skip_rate_limit=True)
    container = application.container

    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    container.db_session.override(providers.Factory(test_session_factory))

    mock_process = AsyncMock()
    mock_process.execute = AsyncMock(return_value=None)
    container.process_document_use_case.override(providers.Object(mock_process))
    container.vector_store.override(providers.Object(AsyncMock()))
    container.cache_service.override(providers.Singleton(InMemoryCacheService))

    yield application

    container.db_session.reset_override()
    container.process_document_use_case.reset_override()
    container.vector_store.reset_override()
    container.cache_service.reset_override()


class APIHelper:
    def __init__(self, fastapi_app):
        self._app = fastapi_app

    def _request(self, method: str, url: str, **kwargs):
        async def _do():
            transport = ASGITransport(app=self._app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                return await getattr(c, method)(url, **kwargs)
        return _run(_do())

    def get(self, url, **kwargs):
        return self._request("get", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("post", url, **kwargs)

    def put(self, url, **kwargs):
        return self._request("put", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._request("patch", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._request("delete", url, **kwargs)


@pytest.fixture
def client(app) -> APIHelper:
    return APIHelper(app)


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    resp = client.post("/api/v1/tenants", json={"name": "e2e-tenant"})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}
