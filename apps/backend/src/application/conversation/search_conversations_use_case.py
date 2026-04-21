"""Search Conversations Use Case — S-Gov.6b

兩種搜尋模式：
- keyword：PG ILIKE on conversations.summary（精準字面）
- semantic：Milvus vector search on conv_summaries collection（語意相近）

Semantic 模式內部會呼叫 embedding service 一次（admin 操作 token），
歸帳到 SYSTEM tenant + UsageCategory.EMBEDDING（admin 行為慣例）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.conversation.entity import Conversation
from src.domain.conversation.repository import ConversationRepository
from src.domain.rag.services import EmbeddingService
from src.domain.rag.value_objects import TokenUsage
from src.domain.tenant.repository import TenantRepository
from src.domain.usage.category import UsageCategory
from src.infrastructure.milvus.milvus_vector_store import MilvusVectorStore

logger = logging.getLogger(__name__)


# 既有約定：admin 行為歸帳給 SYSTEM tenant
_SYSTEM_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class ConversationSearchResultItem:
    conversation_id: str
    tenant_id: str
    tenant_name: str
    bot_id: str | None
    summary: str
    first_message_at: str | None
    last_message_at: str | None
    message_count: int
    score: float | None  # 僅 semantic 模式有
    matched_via: str  # "keyword" | "semantic"


class SearchConversationsUseCase:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        tenant_repository: TenantRepository,
        embedding_service: EmbeddingService,
        vector_store: MilvusVectorStore,
        record_usage: RecordUsageUseCase,
    ) -> None:
        self._conv_repo = conversation_repository
        self._tenant_repo = tenant_repository
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._record_usage = record_usage

    async def search_by_keyword(
        self,
        *,
        keyword: str,
        tenant_id: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
    ) -> list[ConversationSearchResultItem]:
        convs = await self._conv_repo.search_summary_by_keyword(
            keyword=keyword,
            tenant_id=tenant_id,
            bot_id=bot_id,
            limit=limit,
        )
        name_map = await self._tenant_name_map(convs)
        return [
            self._to_item(c, score=None, matched_via="keyword", name_map=name_map)
            for c in convs
        ]

    async def search_by_semantic(
        self,
        *,
        query: str,
        tenant_id: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
        score_threshold: float = 0.3,
    ) -> list[ConversationSearchResultItem]:
        # Step 1: embed query（admin 操作 token 歸 SYSTEM tenant）
        query_vector = await self._embedding.embed_query(query)
        embedding_tokens = int(
            getattr(self._embedding, "last_total_tokens", 0) or 0
        )
        embedding_model = str(
            getattr(self._embedding, "_model", "text-embedding-3-large")
        )
        if embedding_tokens > 0:
            await self._record_usage.execute(
                tenant_id=_SYSTEM_TENANT_ID,
                request_type=UsageCategory.EMBEDDING.value,
                usage=TokenUsage(
                    model=embedding_model,
                    input_tokens=embedding_tokens,
                    output_tokens=0,
                    total_tokens=embedding_tokens,
                ),
                bot_id=None,
            )

        # Step 2: Milvus search
        try:
            hits = await self._vector_store.search_conv_summaries(
                query_vector=query_vector,
                tenant_id=tenant_id,
                bot_id=bot_id,
                limit=limit,
                score_threshold=score_threshold,
            )
        except Exception:
            logger.warning(
                "conv_search.milvus_failed",
                extra={"query": query[:50]},
                exc_info=True,
            )
            return []

        # Step 3: hydrate from PG（補 tenant_name + 最新 conversation header）
        conv_ids = [h.id for h in hits]
        score_by_id = {h.id: h.score for h in hits}
        convs = await self._conv_repo.find_by_ids(conv_ids)
        name_map = await self._tenant_name_map(convs)
        # 維持 hits 排序（按 score desc）
        conv_by_id = {c.id.value: c for c in convs}
        items: list[ConversationSearchResultItem] = []
        for cid in conv_ids:
            c = conv_by_id.get(cid)
            if c is None:
                continue  # PG 沒對應（可能 race）— 跳過
            items.append(
                self._to_item(
                    c,
                    score=score_by_id.get(cid),
                    matched_via="semantic",
                    name_map=name_map,
                )
            )
        return items

    async def _tenant_name_map(
        self, convs: list[Conversation]
    ) -> dict[str, str]:
        """補 tenant_name（一次抓全部 tenants 建 dict）"""
        if not convs:
            return {}
        tenants = await self._tenant_repo.find_all()
        return {t.id.value: t.name for t in tenants}

    @staticmethod
    def _to_item(
        c: Conversation,
        *,
        score: float | None,
        matched_via: str,
        name_map: dict[str, str],
    ) -> ConversationSearchResultItem:
        return ConversationSearchResultItem(
            conversation_id=c.id.value,
            tenant_id=c.tenant_id,
            tenant_name=name_map.get(c.tenant_id, ""),
            bot_id=c.bot_id,
            summary=c.summary or "",
            first_message_at=c.created_at.isoformat() if c.created_at else None,
            last_message_at=c.last_message_at.isoformat()
            if c.last_message_at
            else None,
            message_count=c.message_count,
            score=score,
            matched_via=matched_via,
        )
