"""Wiki query end-to-end integration test.

真實 PostgreSQL，假 LLM（KeywordBFSNavigator 用 mock LLM 抽關鍵字），
驗證從 DB 載入 wiki graph → navigator 找節點 → tool response schema 全鏈路。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.application.wiki.query_wiki_use_case import (
    QueryWikiCommand,
    QueryWikiUseCase,
)
from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.domain.wiki.entity import WikiGraph
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.repositories.wiki_graph_repository import (
    SQLAlchemyWikiGraphRepository,
)
from src.infrastructure.wiki.keyword_bfs_navigator import KeywordBFSNavigator

TEST_DB_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag_test"
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def session_factory(_test_db):
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    yield factory
    _run(engine.dispose())


def _llm_returning(text: str) -> MagicMock:
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=LLMResult(
            text=text,
            usage=TokenUsage(
                model="fake",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                estimated_cost=0.0001,
            ),
        )
    )
    return mock


def _seed_tenant_and_bot(
    session_factory, tenant_id: str, bot_id: str
) -> None:
    """Create minimum tenant + bot row for FK to work."""

    async def _seed():
        async with session_factory() as session:
            session.add(
                TenantModel(
                    id=tenant_id,
                    name=f"tenant-{tenant_id[:8]}",
                    plan="starter",
                )
            )
            await session.flush()
            session.add(
                BotModel(
                    id=bot_id,
                    short_code=f"sc-{bot_id[:6]}",
                    tenant_id=tenant_id,
                    name="wiki-bot",
                    description="",
                    is_active=True,
                    system_prompt="",
                    enabled_tools=["rag_query"],
                    llm_provider="",
                    llm_model="",
                    show_sources=True,
                    mcp_servers=[],
                    mcp_bindings=[],
                    max_tool_calls=5,
                    audit_mode="minimal",
                    eval_depth="L1",
                    base_prompt="",
                    fab_icon_url="",
                    widget_enabled=False,
                    widget_allowed_origins=[],
                    widget_keep_history=True,
                    widget_welcome_message="",
                    widget_placeholder_text="",
                    widget_greeting_messages=[],
                    widget_greeting_animation="fade",
                    memory_enabled=False,
                    memory_extraction_threshold=3,
                    memory_extraction_prompt="",
                    line_show_sources=False,
                    temperature=0.3,
                    max_tokens=1024,
                    history_limit=10,
                    frequency_penalty=0.0,
                    reasoning_effort="medium",
                    rag_top_k=5,
                    rag_score_threshold=0.3,
                    knowledge_mode="wiki",
                    wiki_navigation_strategy="keyword_bfs",
                )
            )
            await session.commit()

    _run(_seed())


def _seed_wiki_graph(
    session_factory, tenant_id: str, bot_id: str
) -> None:
    """Insert a pre-compiled wiki graph for the test bot."""

    async def _save():
        async with session_factory() as session:
            repo = SQLAlchemyWikiGraphRepository(session)
            graph = WikiGraph(
                tenant_id=tenant_id,
                bot_id=bot_id,
                kb_id=str(uuid4()),  # Test doesn't enforce kb existence
                status="ready",
                nodes={
                    "退貨政策": {
                        "label": "退貨政策",
                        "type": "policy",
                        "summary": "30 天內可退貨",
                        "source_doc_ids": ["doc-001"],
                    },
                    "退款流程": {
                        "label": "退款流程",
                        "type": "process",
                        "summary": "信用卡退款 5-7 日到帳",
                        "source_doc_ids": ["doc-002"],
                    },
                    "聯絡客服": {
                        "label": "聯絡客服",
                        "type": "process",
                        "summary": "週一至週五 9-18 點",
                        "source_doc_ids": ["doc-003"],
                    },
                },
                edges={
                    "e1": {
                        "source": "退貨政策",
                        "target": "退款流程",
                        "relation": "triggers",
                        "confidence": "EXTRACTED",
                        "score": 1.0,
                    },
                    "e2": {
                        "source": "退貨政策",
                        "target": "聯絡客服",
                        "relation": "requires",
                        "confidence": "EXTRACTED",
                        "score": 1.0,
                    },
                },
                backlinks={
                    "退款流程": ["退貨政策"],
                    "聯絡客服": ["退貨政策"],
                },
                clusters=[
                    {
                        "id": "cluster-0000",
                        "label": "退貨相關",
                        "node_ids": ["退貨政策", "退款流程", "聯絡客服"],
                        "summary": "",
                    }
                ],
                metadata={"doc_count": 3},
                compiled_at=datetime.now(timezone.utc),
            )
            await repo.save(graph)

    _run(_save())


# Cannot use kb FK without a knowledge_bases row — but the wiki_graphs table
# has FK to knowledge_bases. Need to insert one or skip FK by using existing
# tests' approach. Re-using the helper from test_compile_wiki_e2e style.
def _seed_kb_and_link(
    session_factory, tenant_id: str, bot_id: str, kb_id: str
) -> None:
    from src.infrastructure.db.models.knowledge_base_model import (
        KnowledgeBaseModel,
    )

    async def _seed():
        async with session_factory() as session:
            session.add(
                KnowledgeBaseModel(
                    id=kb_id,
                    tenant_id=tenant_id,
                    name="test-kb",
                    description="",
                    kb_type="user",
                )
            )
            await session.commit()

    _run(_seed())


class TestQueryWikiE2E:
    def test_query_finds_seed_and_neighbors(self, session_factory):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_tenant_and_bot(session_factory, tenant_id, bot_id)
        _seed_kb_and_link(session_factory, tenant_id, bot_id, kb_id)

        # Save wiki graph with explicit kb_id matching the seeded kb
        async def _save_graph():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                graph = WikiGraph(
                    tenant_id=tenant_id,
                    bot_id=bot_id,
                    kb_id=kb_id,
                    status="ready",
                    nodes={
                        "退貨政策": {
                            "label": "退貨政策",
                            "type": "policy",
                            "summary": "30 天內可退貨",
                            "source_doc_ids": ["doc-001"],
                        },
                        "退款流程": {
                            "label": "退款流程",
                            "type": "process",
                            "summary": "5-7 日到帳",
                            "source_doc_ids": ["doc-002"],
                        },
                    },
                    edges={
                        "e1": {
                            "source": "退貨政策",
                            "target": "退款流程",
                            "relation": "triggers",
                            "confidence": "EXTRACTED",
                            "score": 1.0,
                        },
                    },
                    metadata={"doc_count": 2},
                    compiled_at=datetime.now(timezone.utc),
                )
                await repo.save(graph)

        _run(_save_graph())

        # Now query with KeywordBFSNavigator
        async def _query():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                navigator = KeywordBFSNavigator(
                    llm_service=_llm_returning('["退貨"]')
                )
                use_case = QueryWikiUseCase(
                    wiki_graph_repository=repo,
                    navigators={"keyword_bfs": navigator},
                )
                return await use_case.execute(
                    QueryWikiCommand(
                        tenant_id=tenant_id,
                        bot_id=bot_id,
                        query="退貨怎麼辦？",
                        navigation_strategy="keyword_bfs",
                    )
                )

        result = _run(_query())

        # Verify
        assert result.tool_response["success"] is True
        assert len(result.nodes) >= 2  # seed + at least 1 neighbor
        node_labels = [n.label for n in result.nodes]
        assert "退貨政策" in node_labels
        assert "退款流程" in node_labels  # via BFS

        # Schema check
        sources = result.tool_response["sources"]
        assert len(sources) >= 2
        for s in sources:
            assert "document_name" in s
            assert "content_snippet" in s
            assert "score" in s
            assert "chunk_id" in s
            assert "document_id" in s

    def test_query_no_wiki_graph_returns_readable_error(
        self, session_factory
    ):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        _seed_tenant_and_bot(session_factory, tenant_id, bot_id)
        # Note: NO wiki graph saved

        async def _query():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                navigator = KeywordBFSNavigator(
                    llm_service=_llm_returning('["test"]')
                )
                use_case = QueryWikiUseCase(
                    wiki_graph_repository=repo,
                    navigators={"keyword_bfs": navigator},
                )
                return await use_case.execute(
                    QueryWikiCommand(
                        tenant_id=tenant_id,
                        bot_id=bot_id,
                        query="任何問題",
                        navigation_strategy="keyword_bfs",
                    )
                )

        result = _run(_query())
        assert result.tool_response["success"] is True
        assert "尚未編譯" in result.tool_response["context"]
        assert result.tool_response["sources"] == []

    def test_bot_with_wiki_navigation_strategy_persisted_correctly(
        self, session_factory
    ):
        """Verify that bot.wiki_navigation_strategy is persisted to DB."""
        from src.infrastructure.db.repositories.bot_repository import (
            SQLAlchemyBotRepository,
        )

        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        _seed_tenant_and_bot(session_factory, tenant_id, bot_id)

        async def _check():
            async with session_factory() as session:
                bot_repo = SQLAlchemyBotRepository(session)
                bot = await bot_repo.find_by_id(bot_id)
                return bot

        bot = _run(_check())
        assert bot is not None
        assert bot.knowledge_mode == "wiki"
        assert bot.wiki_navigation_strategy == "keyword_bfs"
