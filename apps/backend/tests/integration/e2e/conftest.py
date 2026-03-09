"""E2E Integration Test Fixtures — full user journey tests.

These tests exercise complete user flows: tenant → KB → document → Bot → chat.
Real DB, mock Qdrant/Embedding/LLM for deterministic behaviour.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import providers
from langchain_core.messages import AIMessage

from src.domain.rag.value_objects import SearchResult
from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.embedding.fake_embedding_service import FakeEmbeddingService


# -----------------------------------------------------------------------
# E2E app fixture — Router mode (mock agent via container selector)
# -----------------------------------------------------------------------


@pytest.fixture
def e2e_app(test_engine):
    """E2E app: real DB + real chunking + mock Qdrant + mock LLM (router)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.main import create_app

    application = create_app(skip_rate_limit=True)
    container = application.container

    # DB → test engine
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    container.db_session.override(providers.Factory(test_session_factory))
    container.trace_session_factory.override(
        providers.Object(test_session_factory)
    )

    # Qdrant vector_store → mock returning SearchResult objects
    mock_vector = AsyncMock()
    mock_vector.search.return_value = [
        SearchResult(
            id="chunk-e2e-001",
            score=0.92,
            payload={
                "content": "退貨政策：購買後 30 天內可無條件退貨，請保留原始包裝。",
                "document_name": "退貨政策.txt",
                "document_id": "doc-e2e-001",
                "tenant_id": "e2e-tenant",
            },
        ),
    ]
    mock_vector.upsert = AsyncMock(return_value=None)
    mock_vector.delete_by_document_id = AsyncMock(return_value=None)
    container.vector_store.override(providers.Object(mock_vector))

    # Embedding → FakeEmbeddingService (deterministic vectors)
    container.embedding_service.override(
        providers.Singleton(FakeEmbeddingService)
    )

    # Cache → in-memory (no Redis)
    container.cache_service.override(
        providers.Singleton(InMemoryCacheService)
    )

    yield application

    container.db_session.reset_override()
    container.trace_session_factory.reset_override()
    container.vector_store.reset_override()
    container.embedding_service.reset_override()
    container.cache_service.reset_override()


# -----------------------------------------------------------------------
# E2E app fixture — ReAct mode (mock LLM via provider override)
# -----------------------------------------------------------------------


def _build_react_mock_llm():
    """Create a fresh MagicMock LLM with rag_query → answer side_effect."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            # Step 1: agent calls rag_query tool
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "rag_query",
                        "args": {"query": "退貨流程是什麼？"},
                        "id": "call_e2e_1",
                    }
                ],
            ),
            # Step 2: agent produces final answer
            AIMessage(
                content="根據查詢結果：退貨流程說明 — 30 天內可退貨，保留包裝。"
            ),
        ]
    )
    return mock_llm


@pytest.fixture
def e2e_app_react(e2e_app):
    """E2E app with mocked ReAct LLM for deterministic tool-call cycles.

    Overrides react_agent_service provider with a patched singleton so that
    every SendMessageUseCase gets the same service with mock _resolve_llm_model.
    """
    container = e2e_app.container

    # Get a real service instance, then patch its _resolve_llm_model
    service = container.react_agent_service()
    mock_llm = _build_react_mock_llm()
    service._resolve_llm_model = AsyncMock(return_value=mock_llm)

    # Override the provider so all consumers get this patched instance
    container.react_agent_service.override(providers.Object(service))

    yield e2e_app

    container.react_agent_service.reset_override()


# -----------------------------------------------------------------------
# E2E API clients
# -----------------------------------------------------------------------


@pytest.fixture
def e2e_client(e2e_app):
    """APIHelper bound to e2e_app (Router mode)."""
    from tests.integration.conftest import APIHelper

    return APIHelper(e2e_app)


@pytest.fixture
def e2e_react_client(e2e_app_react):
    """APIHelper bound to e2e_app_react (ReAct mode)."""
    from tests.integration.conftest import APIHelper

    return APIHelper(e2e_app_react)


# -----------------------------------------------------------------------
# Shared step helpers
# -----------------------------------------------------------------------


def create_tenant_and_login(client, name: str) -> dict:
    """Create tenant + get JWT, return headers dict with _tenant_id."""
    resp = client.post("/api/v1/tenants", json={"name": name})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    token_resp = client.post(
        "/api/v1/auth/token", json={"tenant_id": tenant_id}
    )
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
        "_tenant_id": tenant_id,
    }


def auth_only(headers: dict) -> dict:
    """Strip internal keys (starting with _) from headers."""
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def create_kb(client, headers: dict, name: str) -> str:
    """Create a knowledge base, return its ID."""
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=auth_only(headers),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def upload_doc(
    client, headers: dict, kb_id: str, filename: str, content: str
) -> dict:
    """Upload a document to a KB, return response JSON."""
    resp = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={
            "file": (filename, content.encode(), "text/plain"),
        },
        headers=auth_only(headers),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_bot(
    client,
    headers: dict,
    name: str,
    kb_ids: list[str],
    agent_mode: str = "router",
    **kwargs,
) -> str:
    """Create a Bot bound to KBs, return bot ID."""
    body = {
        "name": name,
        "knowledge_base_ids": kb_ids,
        "agent_mode": agent_mode,
        **kwargs,
    }
    resp = client.post(
        "/api/v1/bots",
        json=body,
        headers=auth_only(headers),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def send_chat(
    client,
    headers: dict,
    bot_id: str,
    message: str,
    conversation_id: str | None = None,
) -> dict:
    """Send a chat message via agent API, return response dict."""
    body: dict = {"bot_id": bot_id, "message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id

    resp = client.post(
        "/api/v1/agent/chat",
        json=body,
        headers=auth_only(headers),
    )
    return {"status_code": resp.status_code, **resp.json()}


def enable_react_mode(client, headers: dict) -> None:
    """PATCH tenant to allow react agent mode."""
    tenant_id = headers["_tenant_id"]
    resp = client.patch(
        f"/api/v1/tenants/{tenant_id}/agent-modes",
        json={"allowed_agent_modes": ["router", "react"]},
        headers=auth_only(headers),
    )
    assert resp.status_code == 200, resp.text
