"""商品推薦工具 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.domain.rag.value_objects import RAGResponse, Source, TokenUsage
from src.domain.shared.exceptions import NoRelevantKnowledgeError
from src.infrastructure.langgraph.tools import ProductRecommendTool

scenarios("unit/agent/product_recommend.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_system_kb(tenant_id: str = "tenant-001") -> KnowledgeBase:
    return KnowledgeBase(
        id=KnowledgeBaseId(value="kb-system-001"),
        tenant_id=tenant_id,
        name="商品目錄",
        description="系統商品目錄",
        kb_type="system",
    )


@given("租戶有系統知識庫")
def tenant_has_system_kb(context):
    mock_kb_repo = AsyncMock()
    mock_kb_repo.find_system_kbs = AsyncMock(
        return_value=[_make_system_kb()]
    )

    mock_rag_use_case = AsyncMock()
    mock_rag_use_case.execute = AsyncMock(
        return_value=RAGResponse(
            answer="推薦您選購 Bluetooth Speaker，適合日常使用。",
            sources=[
                Source(
                    document_name="product_catalog_batch_1.txt",
                    content_snippet="Bluetooth Speaker — electronics",
                    score=0.85,
                    chunk_id="chunk-001",
                ),
            ],
            query="推薦一個電子產品",
            tenant_id="tenant-001",
            knowledge_base_id="kb-system-001",
            usage=TokenUsage(
                model="test", input_tokens=10, output_tokens=20,
                total_tokens=30, estimated_cost=0.0,
            ),
        )
    )

    context["tool"] = ProductRecommendTool(
        query_rag_use_case=mock_rag_use_case,
        kb_repository=mock_kb_repo,
    )
    context["tenant_id"] = "tenant-001"


@given("租戶沒有系統知識庫")
def tenant_has_no_system_kb(context):
    mock_kb_repo = AsyncMock()
    mock_kb_repo.find_system_kbs = AsyncMock(return_value=[])

    mock_rag_use_case = AsyncMock()

    context["tool"] = ProductRecommendTool(
        query_rag_use_case=mock_rag_use_case,
        kb_repository=mock_kb_repo,
    )
    context["tenant_id"] = "tenant-001"


@given("租戶有系統知識庫但無相關商品")
def tenant_has_system_kb_no_match(context):
    mock_kb_repo = AsyncMock()
    mock_kb_repo.find_system_kbs = AsyncMock(
        return_value=[_make_system_kb()]
    )

    mock_rag_use_case = AsyncMock()
    mock_rag_use_case.execute = AsyncMock(
        side_effect=NoRelevantKnowledgeError("不存在的商品類別 XYZ")
    )

    context["tool"] = ProductRecommendTool(
        query_rag_use_case=mock_rag_use_case,
        kb_repository=mock_kb_repo,
    )
    context["tenant_id"] = "tenant-001"


@when('請求推薦 "推薦一個電子產品"')
def recommend_electronics(context):
    context["result"] = _run(
        context["tool"].invoke(context["tenant_id"], "推薦一個電子產品")
    )


@when('請求推薦 "不存在的商品類別 XYZ"')
def recommend_nonexistent(context):
    context["result"] = _run(
        context["tool"].invoke(context["tenant_id"], "不存在的商品類別 XYZ")
    )


@then("應回傳成功的推薦結果")
def verify_success(context):
    assert context["result"]["success"] is True


@then("結果應包含推薦答案")
def verify_has_answer(context):
    assert context["result"]["answer"]
    assert len(context["result"]["sources"]) > 0


@then("應回傳尚未建立商品目錄的錯誤")
def verify_no_catalog_error(context):
    assert context["result"]["success"] is False
    assert "尚未建立商品目錄" in context["result"]["error"]


@then("結果應提示找不到相關商品")
def verify_no_relevant_products(context):
    assert "沒有找到相關商品" in context["result"]["answer"]
    assert context["result"]["sources"] == []
