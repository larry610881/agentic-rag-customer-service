"""WikiGraphRepository integration tests — real PostgreSQL.

驗證 wiki_graphs 表的 CRUD、JSONB 儲存、多租戶隔離。
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.value_objects import WikiGraphId, WikiStatus
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.repositories.wiki_graph_repository import (
    SQLAlchemyWikiGraphRepository,
)

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


def _seed_tenant_bot_kb(
    session_factory, tenant_id: str, bot_id: str, kb_id: str
) -> None:
    """Create minimum parent rows (tenant → kb, bot) before inserting wiki_graph."""

    async def _seed():
        async with session_factory() as session:
            session.add(
                TenantModel(
                    id=tenant_id,
                    name=f"tenant-{tenant_id[:8]}",
                    plan="starter",
                )
            )
            await session.flush()  # Force tenant INSERT before children
            session.add(
                KnowledgeBaseModel(
                    id=kb_id,
                    tenant_id=tenant_id,
                    name="test-kb",
                    description="",
                    kb_type="user",
                )
            )
            await session.flush()
            session.add(
                BotModel(
                    id=bot_id,
                    short_code=f"sc-{bot_id[:6]}",
                    tenant_id=tenant_id,
                    name="test-bot",
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
                )
            )
            await session.commit()

    _run(_seed())


class TestWikiGraphRepositoryCRUD:
    def test_save_and_find_by_id(self, session_factory):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_tenant_bot_kb(session_factory, tenant_id, bot_id, kb_id)

        graph = WikiGraph(
            id=WikiGraphId(),
            tenant_id=tenant_id,
            bot_id=bot_id,
            kb_id=kb_id,
            status=WikiStatus.READY.value,
            nodes={
                "n1": {"label": "退貨流程", "type": "process"},
                "n2": {"label": "退款政策", "type": "policy"},
            },
            edges={
                "e1": {
                    "source": "n1",
                    "target": "n2",
                    "relation": "requires",
                    "confidence": "EXTRACTED",
                    "score": 1.0,
                },
            },
            backlinks={"n2": ["n1"]},
            clusters=[
                {"id": "c1", "label": "退貨相關", "node_ids": ["n1", "n2"]}
            ],
            metadata={"doc_count": 2, "token_usage": {"input": 100}},
            compiled_at=datetime.now(timezone.utc),
        )

        async def _scenario():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(graph)

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                loaded = await repo.find_by_id(graph.id.value)
                assert loaded is not None
                assert loaded.tenant_id == tenant_id
                assert loaded.bot_id == bot_id
                assert loaded.kb_id == kb_id
                assert loaded.status == "ready"
                assert loaded.nodes["n1"]["label"] == "退貨流程"
                assert loaded.edges["e1"]["relation"] == "requires"
                assert loaded.backlinks == {"n2": ["n1"]}
                assert loaded.clusters[0]["label"] == "退貨相關"
                assert loaded.metadata["doc_count"] == 2
                assert loaded.compiled_at is not None

        _run(_scenario())

    def test_find_by_bot_id(self, session_factory):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_tenant_bot_kb(session_factory, tenant_id, bot_id, kb_id)

        graph = WikiGraph(
            tenant_id=tenant_id,
            bot_id=bot_id,
            kb_id=kb_id,
            status="pending",
        )

        async def _scenario():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(graph)

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                loaded = await repo.find_by_bot_id(tenant_id, bot_id)
                assert loaded is not None
                assert loaded.id.value == graph.id.value

        _run(_scenario())

    def test_find_by_bot_id_wrong_tenant_returns_none(self, session_factory):
        """Tenant isolation: 其他租戶查不到這個 wiki_graph。"""
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_tenant_bot_kb(session_factory, tenant_a, bot_id, kb_id)

        graph = WikiGraph(
            tenant_id=tenant_a, bot_id=bot_id, kb_id=kb_id
        )

        async def _scenario():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(graph)

            # Need tenant_b to exist for subsequent queries
            async with session_factory() as session:
                session.add(
                    TenantModel(
                        id=tenant_b,
                        name=f"tenant-b-{tenant_b[:8]}",
                        plan="starter",
                    )
                )
                await session.flush()
                await session.commit()

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                # Query with tenant_b - should find nothing
                loaded = await repo.find_by_bot_id(tenant_b, bot_id)
                assert loaded is None

        _run(_scenario())

    def test_update_existing_graph(self, session_factory):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_tenant_bot_kb(session_factory, tenant_id, bot_id, kb_id)

        graph_id = WikiGraphId()
        graph = WikiGraph(
            id=graph_id,
            tenant_id=tenant_id,
            bot_id=bot_id,
            kb_id=kb_id,
            status="pending",
            nodes={},
        )

        async def _scenario():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(graph)

            # Update the graph
            graph.status = "ready"
            graph.nodes = {"n1": {"label": "New Node"}}
            graph.metadata = {"updated": True}

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(graph)

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                loaded = await repo.find_by_id(graph_id.value)
                assert loaded is not None
                assert loaded.status == "ready"
                assert loaded.nodes == {"n1": {"label": "New Node"}}
                assert loaded.metadata == {"updated": True}

        _run(_scenario())

    def test_delete_by_bot_id(self, session_factory):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_tenant_bot_kb(session_factory, tenant_id, bot_id, kb_id)

        graph = WikiGraph(
            tenant_id=tenant_id, bot_id=bot_id, kb_id=kb_id
        )

        async def _scenario():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(graph)

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.delete_by_bot_id(tenant_id, bot_id)

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                loaded = await repo.find_by_bot_id(tenant_id, bot_id)
                assert loaded is None

        _run(_scenario())

    def test_find_all_by_tenant_only_returns_own_tenant(self, session_factory):
        """Tenant isolation: find_all_by_tenant 只回傳該租戶的 wiki_graphs。"""
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        bot_a = str(uuid4())
        bot_b = str(uuid4())
        kb_a = str(uuid4())
        kb_b = str(uuid4())
        _seed_tenant_bot_kb(session_factory, tenant_a, bot_a, kb_a)
        _seed_tenant_bot_kb(session_factory, tenant_b, bot_b, kb_b)

        g_a = WikiGraph(tenant_id=tenant_a, bot_id=bot_a, kb_id=kb_a)
        g_b = WikiGraph(tenant_id=tenant_b, bot_id=bot_b, kb_id=kb_b)

        async def _scenario():
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                await repo.save(g_a)
                await repo.save(g_b)

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                results_a = await repo.find_all_by_tenant(tenant_a)
                assert len(results_a) == 1
                assert results_a[0].tenant_id == tenant_a

                count_a = await repo.count_by_tenant(tenant_a)
                count_b = await repo.count_by_tenant(tenant_b)
                assert count_a == 1
                assert count_b == 1

        _run(_scenario())
