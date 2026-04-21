"""Generate Conversation Summary Use Case — S-Gov.6b

由 worker arq job 觸發：對單一 conversation 生 LLM 摘要 + embedding，
upsert 進 Milvus，update PG。內含 2 次 RecordUsageUseCase 呼叫
（CONVERSATION_SUMMARY + EMBEDDING）。

Race-safe：snapshot message_count 在 LLM 呼叫前。下次 cron 掃時若 conv
又新增 message，summary_message_count < message_count 會再觸發重生。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.summary_service import ConversationSummaryService
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory
from src.infrastructure.milvus.milvus_vector_store import MilvusVectorStore

logger = logging.getLogger(__name__)


class GenerateConversationSummaryUseCase:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        summary_service: ConversationSummaryService,
        vector_store: MilvusVectorStore,
        record_usage: RecordUsageUseCase,
    ) -> None:
        self._conv_repo = conversation_repository
        self._summary_service = summary_service
        self._vector_store = vector_store
        self._record_usage = record_usage

    async def execute(self, conversation_id: str) -> dict:
        """生 summary + embed + upsert + 兩次 record_usage。"""
        conv = await self._conv_repo.find_by_id(conversation_id)
        if conv is None:
            return {"skipped": "not_found"}

        if not conv.messages:
            return {"skipped": "empty"}

        # snapshot message_count（race-safe）
        n_at_start = conv.message_count or len(conv.messages)

        # 生 summary + embedding
        try:
            result = await self._summary_service.summarize(
                messages=[
                    {"role": m.role, "content": m.content} for m in conv.messages
                ],
            )
        except Exception:
            logger.warning(
                "conv_summary.llm_failed",
                extra={"conversation_id": conversation_id},
                exc_info=True,
            )
            return {"failed": "llm_error"}

        # === Token tracking 兩次呼叫 ===
        # 1. LLM 摘要
        await self._record_usage.execute(
            tenant_id=conv.tenant_id,
            request_type=UsageCategory.CONVERSATION_SUMMARY.value,
            usage=TokenUsage(
                model=result.summary_model,
                input_tokens=result.summary_input_tokens,
                output_tokens=result.summary_output_tokens,
                total_tokens=result.summary_input_tokens
                + result.summary_output_tokens,
            ),
            bot_id=conv.bot_id,
        )
        # 2. Embedding
        if result.embedding_tokens > 0:
            await self._record_usage.execute(
                tenant_id=conv.tenant_id,
                request_type=UsageCategory.EMBEDDING.value,
                usage=TokenUsage(
                    model=result.embedding_model,
                    input_tokens=result.embedding_tokens,
                    output_tokens=0,
                    total_tokens=result.embedding_tokens,
                ),
                bot_id=conv.bot_id,
            )

        # === Persist ===
        # Upsert Milvus（同 conv_id 自動覆蓋）
        first_msg_at = conv.messages[0].created_at if conv.messages else None
        now = datetime.now(timezone.utc)
        try:
            await self._vector_store.upsert_conv_summary(
                conversation_id=conversation_id,
                embedding=result.embedding,
                tenant_id=conv.tenant_id,
                bot_id=conv.bot_id,
                summary=result.summary,
                first_message_at=first_msg_at.isoformat()
                if first_msg_at
                else None,
                message_count=n_at_start,
                summary_at=now.isoformat(),
            )
        except Exception:
            logger.warning(
                "conv_summary.milvus_failed",
                extra={"conversation_id": conversation_id},
                exc_info=True,
            )
            # 不阻擋 PG 寫入 — 下次 cron 會重試 upsert

        # Update PG（snapshot N，後續 cron query 用以判斷是否需重生）
        conv.summary = result.summary
        conv.summary_message_count = n_at_start
        conv.summary_at = now
        await self._conv_repo.save(conv)

        return {
            "summary": result.summary,
            "summary_tokens": result.summary_input_tokens
            + result.summary_output_tokens,
            "embedding_tokens": result.embedding_tokens,
            "message_count_at_start": n_at_start,
        }
