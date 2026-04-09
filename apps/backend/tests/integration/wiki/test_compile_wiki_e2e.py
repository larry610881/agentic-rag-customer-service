"""CompileWikiUseCase end-to-end integration test.

真實 PostgreSQL，假 LLM（mock compiler），驗證：
- 從 DB 載入 bot + documents
- 編譯結果正確寫入 wiki_graphs
- metadata 含 token usage + doc count
- 重複編譯會更新同一筆記錄（UNIQUE constraint 不會爆炸）
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.application.wiki.compile_wiki_use_case import (
    CompileWikiCommand,
    CompileWikiUseCase,
)
from src.domain.rag.value_objects import TokenUsage
from src.domain.wiki.services import (
    ExtractedEdge,
    ExtractedGraph,
    ExtractedNode,
    WikiCompilerService,
)
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.document_model import DocumentModel
from src.infrastructure.db.models.knowledge_base_model import (
    KnowledgeBaseModel,
)
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.repositories.bot_repository import (
    SQLAlchemyBotRepository,
)
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
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


class FakeWikiCompiler(WikiCompilerService):
    """Deterministic fake compiler — returns predictable graph per doc."""

    def __init__(self):
        self.calls: list[str] = []

    async def extract(
        self,
        *,
        document_id: str,
        content: str,
        language: str = "zh-TW",
    ) -> ExtractedGraph:
        self.calls.append(document_id)
        return ExtractedGraph(
            nodes=(
                ExtractedNode(
                    id=f"{document_id}_policy",
                    label=f"政策-{document_id[:6]}",
                    type="policy",
                    source_doc_id=document_id,
                ),
                ExtractedNode(
                    id=f"{document_id}_process",
                    label=f"流程-{document_id[:6]}",
                    type="process",
                    source_doc_id=document_id,
                ),
            ),
            edges=(
                ExtractedEdge(
                    source=f"{document_id}_policy",
                    target=f"{document_id}_process",
                    relation="requires",
                    confidence="EXTRACTED",
                    confidence_score=1.0,
                ),
            ),
            usage=TokenUsage(
                model="fake-model",
                input_tokens=50,
                output_tokens=30,
                total_tokens=80,
                estimated_cost=0.0001,
            ),
        )


def _seed_fixtures(
    session_factory, tenant_id: str, bot_id: str, kb_id: str, doc_count: int
) -> list[str]:
    """Create tenant → kb → bot → docs. Returns list of document IDs."""
    doc_ids: list[str] = []

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
                )
            )
            await session.flush()
            # bot_knowledge_bases link
            from src.infrastructure.db.models.bot_knowledge_base_model import (
                BotKnowledgeBaseModel,
            )

            session.add(
                BotKnowledgeBaseModel(
                    bot_id=bot_id,
                    knowledge_base_id=kb_id,
                )
            )
            await session.flush()
            for i in range(doc_count):
                doc_id = str(uuid4())
                doc_ids.append(doc_id)
                session.add(
                    DocumentModel(
                        id=doc_id,
                        kb_id=kb_id,
                        tenant_id=tenant_id,
                        filename=f"faq-{i}.md",
                        content_type="text/markdown",
                        content=(
                            f"文件 {i}：退貨政策說明。"
                            f"顧客可於 30 天內申請退貨，需先聯絡客服。"
                        ),
                        status="completed",
                        chunk_count=1,
                    )
                )
            await session.commit()

    _run(_seed())
    return doc_ids


class TestCompileWikiE2E:
    def test_compile_creates_wiki_graph(self, session_factory):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        doc_ids = _seed_fixtures(
            session_factory, tenant_id, bot_id, kb_id, doc_count=2
        )
        fake_compiler = FakeWikiCompiler()

        async def _scenario():
            async with session_factory() as session:
                use_case = CompileWikiUseCase(
                    bot_repository=SQLAlchemyBotRepository(session),
                    document_repository=SQLAlchemyDocumentRepository(session),
                    wiki_graph_repository=SQLAlchemyWikiGraphRepository(
                        session
                    ),
                    wiki_compiler=fake_compiler,
                )
                result = await use_case.execute(
                    CompileWikiCommand(
                        bot_id=bot_id, tenant_id=tenant_id
                    )
                )

            assert result.document_count == 2
            assert result.node_count == 4  # 2 docs × 2 nodes
            assert result.edge_count == 2  # 2 docs × 1 edge
            assert result.total_usage is not None
            assert result.total_usage.input_tokens == 100  # 2 × 50

            # Verify DB state
            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                loaded = await repo.find_by_bot_id(tenant_id, bot_id)
                assert loaded is not None
                assert loaded.status == "ready"
                assert len(loaded.nodes) == 4
                assert len(loaded.edges) == 2
                assert loaded.metadata["doc_count"] == 2
                assert loaded.metadata["token_usage"]["input"] == 100
                assert loaded.compiled_at is not None

            # Both documents were processed
            assert len(fake_compiler.calls) == 2
            assert set(fake_compiler.calls) == set(doc_ids)

        _run(_scenario())

    def test_compile_empty_kb_produces_empty_ready_graph(
        self, session_factory
    ):
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_fixtures(
            session_factory, tenant_id, bot_id, kb_id, doc_count=0
        )
        fake_compiler = FakeWikiCompiler()

        async def _scenario():
            async with session_factory() as session:
                use_case = CompileWikiUseCase(
                    bot_repository=SQLAlchemyBotRepository(session),
                    document_repository=SQLAlchemyDocumentRepository(session),
                    wiki_graph_repository=SQLAlchemyWikiGraphRepository(
                        session
                    ),
                    wiki_compiler=fake_compiler,
                )
                result = await use_case.execute(
                    CompileWikiCommand(
                        bot_id=bot_id, tenant_id=tenant_id
                    )
                )

            assert result.document_count == 0
            assert result.node_count == 0

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                loaded = await repo.find_by_bot_id(tenant_id, bot_id)
                assert loaded is not None
                assert loaded.status == "ready"
                assert len(loaded.nodes) == 0
            assert fake_compiler.calls == []

        _run(_scenario())

    def test_recompile_overwrites_existing_graph(self, session_factory):
        """Re-running compile should update the same wiki_graphs row,
        not violate UNIQUE(bot_id) constraint."""
        tenant_id = str(uuid4())
        bot_id = str(uuid4())
        kb_id = str(uuid4())
        _seed_fixtures(
            session_factory, tenant_id, bot_id, kb_id, doc_count=1
        )
        fake_compiler = FakeWikiCompiler()

        async def _scenario():
            async with session_factory() as session:
                use_case = CompileWikiUseCase(
                    bot_repository=SQLAlchemyBotRepository(session),
                    document_repository=SQLAlchemyDocumentRepository(session),
                    wiki_graph_repository=SQLAlchemyWikiGraphRepository(
                        session
                    ),
                    wiki_compiler=fake_compiler,
                )
                await use_case.execute(
                    CompileWikiCommand(
                        bot_id=bot_id, tenant_id=tenant_id
                    )
                )

            # Second compile — should update, not insert
            async with session_factory() as session:
                use_case = CompileWikiUseCase(
                    bot_repository=SQLAlchemyBotRepository(session),
                    document_repository=SQLAlchemyDocumentRepository(session),
                    wiki_graph_repository=SQLAlchemyWikiGraphRepository(
                        session
                    ),
                    wiki_compiler=fake_compiler,
                )
                await use_case.execute(
                    CompileWikiCommand(
                        bot_id=bot_id, tenant_id=tenant_id
                    )
                )

            async with session_factory() as session:
                repo = SQLAlchemyWikiGraphRepository(session)
                # Still exactly one graph for this bot
                graphs = await repo.find_all_by_tenant(tenant_id)
                assert len(graphs) == 1
                # Compiler was called twice (once per compile)
                assert len(fake_compiler.calls) == 2

        _run(_scenario())
