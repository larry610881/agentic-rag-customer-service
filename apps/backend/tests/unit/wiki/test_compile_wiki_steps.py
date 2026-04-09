"""CompileWikiUseCase BDD Step Definitions — unit level with AsyncMock.

驗證 use case 編排（bot/doc/compiler/wiki repository 都是 mock），
不走真實 DB 或真實 LLM。
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.wiki.compile_wiki_use_case import (
    CompileWikiCommand,
    CompileWikiUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.knowledge.entity import Document
from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.value_objects import DocumentId
from src.domain.shared.exceptions import ValidationError
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.services import (
    ExtractedEdge,
    ExtractedGraph,
    ExtractedNode,
    WikiCompilerService,
)
from src.domain.wiki.value_objects import WikiGraphId

scenarios("unit/wiki/compile_wiki.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {"saved_graphs": []}


@pytest.fixture
def mock_bot_repo():
    return AsyncMock(spec=BotRepository)


@pytest.fixture
def mock_doc_repo():
    return AsyncMock(spec=DocumentRepository)


@pytest.fixture
def mock_wiki_repo(context):
    repo = AsyncMock(spec=WikiGraphRepository)

    async def _save(graph):
        context["saved_graphs"].append(graph)

    async def _find_by_bot_id(tenant_id, bot_id):
        for g in reversed(context["saved_graphs"]):
            if g.tenant_id == tenant_id and g.bot_id == bot_id:
                return g
        return context.get("existing_graph")

    repo.save.side_effect = _save
    repo.find_by_bot_id.side_effect = _find_by_bot_id
    return repo


@pytest.fixture
def mock_compiler():
    mock = AsyncMock(spec=WikiCompilerService)

    async def _extract(*, document_id, content, language="zh-TW"):
        # Returns a simple 2-node, 1-edge graph for any non-empty doc
        return ExtractedGraph(
            nodes=(
                ExtractedNode(
                    id=f"{document_id}_退貨",
                    label="退貨政策",
                    source_doc_id=document_id,
                ),
                ExtractedNode(
                    id=f"{document_id}_退款",
                    label="退款流程",
                    source_doc_id=document_id,
                ),
            ),
            edges=(
                ExtractedEdge(
                    source=f"{document_id}_退貨",
                    target=f"{document_id}_退款",
                    relation="triggers",
                    confidence="EXTRACTED",
                    confidence_score=1.0,
                ),
            ),
        )

    mock.extract.side_effect = _extract
    return mock


@pytest.fixture
def use_case(mock_bot_repo, mock_doc_repo, mock_wiki_repo, mock_compiler):
    return CompileWikiUseCase(
        bot_repository=mock_bot_repo,
        document_repository=mock_doc_repo,
        wiki_graph_repository=mock_wiki_repo,
        wiki_compiler=mock_compiler,
    )


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('租戶 "{tenant_id}" 存在'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('該租戶已有知識庫 "{kb_id}"'))
def kb_exists(context, kb_id):
    context["kb_id"] = kb_id


@given(parsers.parse('Bot "{bot_id}" 綁定 "{kb_id}"'))
def bot_bound_to_kb(context, mock_bot_repo, bot_id, kb_id):
    bot = Bot(
        id=BotId(value=bot_id),
        tenant_id=context["tenant_id"],
        name=f"bot-{bot_id}",
        knowledge_base_ids=[kb_id],
    )
    context["bot_id"] = bot_id
    context["bot"] = bot
    mock_bot_repo.find_by_id.return_value = bot


@given(parsers.parse('知識庫 "{kb_id}" 內有 {count:d} 份客服文件'))
def kb_has_documents(context, mock_doc_repo, kb_id, count):
    docs = []
    for i in range(count):
        docs.append(
            Document(
                id=DocumentId(value=f"doc-{i:03d}"),
                kb_id=kb_id,
                tenant_id=context["tenant_id"],
                filename=f"faq-{i}.md",
                content_type="text/markdown",
                content=(
                    f"文件 {i} 內容 — 本文件描述退貨政策與退款流程。"
                    f"退貨需聯絡客服，退款於收到貨品後 7 天內處理。"
                ),
                status="completed",
                chunk_count=1,
            )
        )
    mock_doc_repo.find_all_by_kb.return_value = docs


@given(parsers.parse('知識庫 "{kb_id}" 內無任何文件'))
def kb_is_empty(mock_doc_repo, kb_id):
    mock_doc_repo.find_all_by_kb.return_value = []


@given(parsers.parse('Bot "{bot_id}" 未綁定任何知識庫'))
def bot_without_kb(context, mock_bot_repo, bot_id):
    bot = Bot(
        id=BotId(value=bot_id),
        tenant_id=context["tenant_id"],
        name=f"bot-{bot_id}",
        knowledge_base_ids=[],
    )
    context["bot_id"] = bot_id
    mock_bot_repo.find_by_id.return_value = bot


@given(
    parsers.parse(
        'Bot "{bot_id}" 綁定 "{kb_id}" 且已有舊的 WikiGraph'
    )
)
def bot_with_existing_graph(
    context, mock_bot_repo, mock_wiki_repo, bot_id, kb_id
):
    bot = Bot(
        id=BotId(value=bot_id),
        tenant_id=context["tenant_id"],
        name=f"bot-{bot_id}",
        knowledge_base_ids=[kb_id],
    )
    old_graph = WikiGraph(
        id=WikiGraphId(value="old-graph-id"),
        tenant_id=context["tenant_id"],
        bot_id=bot_id,
        kb_id=kb_id,
        status="ready",
        nodes={"old": {"label": "舊節點"}},
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    context["bot_id"] = bot_id
    context["bot"] = bot
    context["existing_graph"] = old_graph
    context["old_updated_at"] = old_graph.updated_at
    mock_bot_repo.find_by_id.return_value = bot


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('觸發 Bot "{bot_id}" 的 Wiki 編譯'))
def trigger_compile(context, use_case, bot_id):
    cmd = CompileWikiCommand(
        bot_id=bot_id, tenant_id=context["tenant_id"]
    )
    context["result"] = _run(use_case.execute(cmd))


@when(parsers.parse('嘗試觸發 Bot "{bot_id}" 的 Wiki 編譯'))
def try_trigger_compile(context, use_case, bot_id):
    cmd = CompileWikiCommand(
        bot_id=bot_id, tenant_id=context["tenant_id"]
    )
    try:
        context["result"] = _run(use_case.execute(cmd))
        context["error"] = None
    except ValidationError as exc:
        context["error"] = exc
        context["result"] = None


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("應建立一筆 WikiGraph 紀錄")
def verify_graph_created(context):
    assert len(context["saved_graphs"]) >= 1


@then(parsers.parse('WikiGraph 狀態應為 "{expected}"'))
def verify_graph_status(context, expected):
    # Last saved graph is the final state
    assert context["saved_graphs"][-1].status == expected


@then(parsers.parse("WikiGraph 應包含至少 {count:d} 個節點"))
def verify_node_count_min(context, count):
    assert len(context["saved_graphs"][-1].nodes) >= count


@then(parsers.parse("WikiGraph 應包含 {count:d} 個節點"))
def verify_node_count_exact(context, count):
    assert len(context["saved_graphs"][-1].nodes) == count


@then("應回傳「未綁定知識庫」錯誤")
def verify_no_kb_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], ValidationError)
    assert "knowledge base" in str(context["error"]).lower()


@then("WikiGraph 的 updated_at 應被更新")
def verify_updated_at_changed(context):
    final = context["saved_graphs"][-1]
    assert final.updated_at > context["old_updated_at"]
