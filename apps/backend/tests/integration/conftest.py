"""Integration Test Fixtures — real PostgreSQL + httpx ASGI + DI override.

Key design decisions:
- ``-p no:asyncio`` in pyproject.toml addopts prevents pytest-asyncio
  from interfering with our manually managed event loops.
- Each ``_run()`` call creates a **fresh** event loop — no cross-loop
  connection issues with asyncpg.
- Per-test: terminate zombie connections → drop_all → create_all gives a
  pristine schema every time (more robust than TRUNCATE).
- NullPool ensures every engine.begin() is a brand-new TCP connection.
"""

import asyncio
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


def _run(coro):
    """Run async code in a fresh event loop (avoids cross-loop issues)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Connection management helpers
# ---------------------------------------------------------------------------


async def _terminate_test_connections():
    """Kill all connections to the test DB and wait until they are gone.

    ``pg_terminate_backend`` sends SIGTERM but returns immediately.  We poll
    ``pg_stat_activity`` until the count reaches 0 so that subsequent DDL
    (like ``DROP TABLE`` / ``CREATE TABLE``) does not deadlock against a
    dying connection that still holds locks.
    """
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
        # Wait until all connections are actually closed (up to 5 s)
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
    """Terminate all connections then drop the test DB."""
    await _terminate_test_connections()
    admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin.dispose()


# ---------------------------------------------------------------------------
# Session-scoped: create / drop test database
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _test_db():
    """Create test DB once per session, drop on teardown."""

    async def _setup():
        await _force_drop_db()

        admin = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        await admin.dispose()

        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    _run(_setup())
    yield

    _run(_force_drop_db())


# ---------------------------------------------------------------------------
# Per-test: kill zombie connections + drop/create all tables
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_db(_test_db):
    """Terminate zombie connections and recreate all tables before each test.

    drop_all + create_all is more robust than TRUNCATE — it handles schema
    corruption and guarantees a pristine state regardless of what the
    previous test did.
    """

    async def _reset():
        await _terminate_test_connections()
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    _run(_reset())


# ---------------------------------------------------------------------------
# Per-test engine (function-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_engine(_test_db):
    """Per-test NullPool engine: yield engine, dispose on teardown."""
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield engine
    _run(engine.dispose())


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
    """Synchronous HTTP helper — each call gets a fresh event loop."""

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
