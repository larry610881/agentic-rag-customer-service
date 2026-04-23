"""E2E Integration Test Fixtures — full user journey tests.

These tests exercise complete user flows: tenant → KB → document → Bot → chat.
Real DB, mock Milvus/Embedding/LLM for deterministic behaviour.
"""

from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers

from src.domain.rag.value_objects import SearchResult
from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.embedding.fake_embedding_service import FakeEmbeddingService


# -----------------------------------------------------------------------
# E2E app fixture (mock agent via container selector)
# -----------------------------------------------------------------------


@pytest.fixture
def e2e_app(test_engine, monkeypatch):
    """E2E app: real DB + real chunking + mock Milvus + mock LLM.

    Integration 測試禁止打付費 OpenAI API：
    - 設 dummy OPENAI_API_KEY 讓 ChatOpenAI init 不炸
    - monkeypatch ReActAgentService._create_chat_model 回 FakeMessagesListChatModel
      （ReAct 會呼叫此 static method 建立 chat model；fake 輸出預先安排的訊息序列）
    """
    import os as _os
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    monkeypatch.setenv(
        "OPENAI_API_KEY", _os.getenv("OPENAI_API_KEY", "sk-test-fake")
    )

    # 替換 ReActAgentService._create_chat_model 為 fake chat model。
    # ReAct 內部會呼叫 `.bind_tools(tools)`，FakeMessagesListChatModel 沒實作
    # 這個 method → subclass 補上（直接回 self，tools 資訊對於預排好的回應無用）
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    class _FakeChatModelWithTools(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):  # type: ignore[override]
            return self

    def _fake_create_chat_model(**kwargs):
        # 預先安排：先要求呼叫 rag_query，再給最終答覆。
        return _FakeChatModelWithTools(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "rag_query",
                            "args": {"query": "退貨流程"},
                            "id": "call_fake_1",
                        }
                    ],
                ),
                AIMessage(
                    content="退貨流程：30 天內無條件退貨，請保留原始包裝。",
                ),
                AIMessage(content="已回答完畢。"),
            ]
        )

    from src.infrastructure.langgraph import react_agent_service as _react_mod

    monkeypatch.setattr(
        _react_mod.ReActAgentService,
        "_create_chat_model",
        staticmethod(_fake_create_chat_model),
    )

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

    # 同步 patch 全域 async_session_factory（同 integration/conftest.py 的做法）
    import sys
    import src.infrastructure.db.engine as _engine_mod

    _orig_factory = _engine_mod.async_session_factory
    monkeypatch.setattr(
        _engine_mod, "async_session_factory", test_session_factory
    )
    for _mod_name, _mod in list(sys.modules.items()):
        if _mod is None or not _mod_name.startswith("src."):
            continue
        if getattr(_mod, "async_session_factory", None) is _orig_factory:
            monkeypatch.setattr(
                _mod, "async_session_factory", test_session_factory
            )

    # Milvus vector_store → mock returning SearchResult objects
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
# E2E API clients
# -----------------------------------------------------------------------


@pytest.fixture
def e2e_client(e2e_app):
    """APIHelper bound to e2e_app."""
    from tests.integration.conftest import APIHelper

    return APIHelper(e2e_app)


# -----------------------------------------------------------------------
# Shared step helpers
# -----------------------------------------------------------------------


def create_tenant_and_login(client, name: str, app=None) -> dict:
    """Create tenant + get JWT, return headers dict with _tenant_id.

    If ``app`` is provided, bootstraps a system_admin JWT first
    (required when the tenant endpoint needs authentication).
    """
    headers = {}
    if app is not None:
        jwt_svc = app.container.jwt_service()
        admin_token = jwt_svc.create_user_token(
            user_id="admin-test", tenant_id=None, role="system_admin",
        )
        headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.post("/api/v1/tenants", json={"name": name}, headers=headers)
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
    **kwargs,
) -> str:
    """Create a Bot bound to KBs, return bot ID."""
    body = {
        "name": name,
        "knowledge_base_ids": kb_ids,
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


