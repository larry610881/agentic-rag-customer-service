"""Integration Test Fixtures — real PostgreSQL + httpx ASGI + DI override.

Key design decisions:
- ``-p no:asyncio`` in pyproject.toml addopts prevents pytest-asyncio
  from interfering with our manually managed event loops.
- Each test gets a **shared event loop** (``_test_loop``) so that all
  asyncpg connections created during the test belong to the same loop.
  When the loop closes at test teardown, connections are cleaned up.
- NullPool ensures every engine.begin() is a brand-new TCP connection.
- ``gc.collect()`` before TRUNCATE flushes dangling connections from the
  previous test before creating new ones.
"""

import asyncio
import gc
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.db.base import Base

# Ensure all ORM models are registered on Base.metadata before create_all
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
    TenantModel,
    UsageRecordModel,
)

ADMIN_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag"
TEST_DB_NAME = "agentic_rag_test"
TEST_DB_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{TEST_DB_NAME}"

# Per-test event loop — set by ``_test_loop`` fixture, used by ``_run()``.
_current_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    """Run async code in the per-test event loop (or a fresh ephemeral one)."""
    loop = _current_loop
    if loop is not None and not loop.is_closed():
        return loop.run_until_complete(coro)
    # Fallback: create ephemeral loop (used by session-scoped fixtures)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Session-scoped: create / drop test database
# ---------------------------------------------------------------------------


async def _force_drop_db():
    """Terminate all connections then drop the test DB."""
    admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                f"WHERE datname = '{TEST_DB_NAME}' "
                "AND pid <> pg_backend_pid()"
            )
        )
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin.dispose()


@pytest.fixture(scope="session")
def test_engine():
    """Create test DB + tables once per session, drop on teardown."""

    async def _setup():
        await _force_drop_db()

        admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        await admin.dispose()

        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return eng

    engine = _run(_setup())
    yield engine

    async def _teardown():
        await engine.dispose()
        await _force_drop_db()

    _run(_teardown())


# ---------------------------------------------------------------------------
# Per-test: shared event loop + TRUNCATE for isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _test_loop():
    """Provide a shared event loop for each test.

    All ``_run()`` calls during the test share this loop, ensuring all
    asyncpg connections belong to the same loop. When the fixture tears
    down, the loop is closed and all connections are cleaned up.
    """
    global _current_loop

    # Force GC to flush dangling connections from previous test
    gc.collect()

    loop = asyncio.new_event_loop()
    _current_loop = loop
    yield loop
    _current_loop = None
    loop.close()


@pytest.fixture(autouse=True)
def clean_tables(test_engine, _test_loop):
    """TRUNCATE all tables before each test scenario."""

    async def _truncate():
        table_names = [t.name for t in reversed(Base.metadata.sorted_tables)]
        if table_names:
            sql = f"TRUNCATE TABLE {', '.join(table_names)} CASCADE"
            async with test_engine.begin() as conn:
                await conn.execute(text(sql))

    _run(_truncate())


# ---------------------------------------------------------------------------
# FastAPI app with DI overrides
# ---------------------------------------------------------------------------


@pytest.fixture
def app(test_engine):
    """Fresh FastAPI app per test with Container overridden for test DB."""
    from src.main import create_app

    application = create_app()
    container = application.container

    # DB session → test engine (NullPool = fresh connection per session)
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    container.db_session.override(providers.Factory(test_session_factory))

    # Skip embedding / Qdrant / document processing
    mock_process = AsyncMock()
    mock_process.execute = AsyncMock(return_value=None)
    container.process_document_use_case.override(providers.Object(mock_process))
    container.vector_store.override(providers.Object(AsyncMock()))

    # Use in-memory cache instead of Redis
    container.cache_service.override(providers.Singleton(InMemoryCacheService))

    yield application

    container.db_session.reset_override()
    container.process_document_use_case.reset_override()
    container.vector_store.reset_override()
    container.cache_service.reset_override()


# ---------------------------------------------------------------------------
# HTTP client (sync wrapper for pytest-bdd def steps)
# ---------------------------------------------------------------------------


class APIHelper:
    """Synchronous HTTP helper — uses the per-test shared event loop."""

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
    """Synchronous HTTP client for use in step definitions."""
    return APIHelper(app)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    """Create a test tenant + JWT token, return Authorization headers.

    Also stores ``_tenant_id`` in the returned dict for convenience.
    """
    resp = client.post("/api/v1/tenants", json={"name": "test-tenant"})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]

    return {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}
