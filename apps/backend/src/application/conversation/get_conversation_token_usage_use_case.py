"""GetConversationTokenUsageUseCase — 單 conversation 的 token 用量聚合

S-ConvInsights.1：admin「對話與追蹤」頁 Token 用量 tab 用。
JOIN messages 取 conversation_id（token_usage_records 只有 message_id，不改 schema）。

### Sprint A+ Bug 1 修復（2026-04-24）

原本 SQL 沒 JOIN `bots` 和 `agent_execution_traces`，前端 fallback 顯示
「未命名機器人」且看不到 channel（web/widget/line/studio）。改為 outerjoin 兩表
取 `bot_name` + `channel_source`，前端可顯示「兩階來源」（bot 名 + channel）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.conversation.repository import ConversationRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.db.models.agent_trace_model import (
    AgentExecutionTraceModel,
)
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel


@dataclass
class GetConversationTokenUsageQuery:
    conversation_id: str
    role: str
    tenant_id: str


@dataclass
class ConversationTokenUsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    estimated_cost: float = 0.0
    message_count: int = 0


@dataclass
class ConversationTokenUsageResult:
    conversation_id: str
    totals: ConversationTokenUsageTotals
    by_request_type: list[dict[str, Any]] = field(default_factory=list)


class GetConversationTokenUsageUseCase:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        session_factory: Any,
    ) -> None:
        self._conv_repo = conversation_repo
        self._session_factory = session_factory

    async def execute(
        self, query: GetConversationTokenUsageQuery
    ) -> ConversationTokenUsageResult:
        # 1. 驗 conversation 存在 + 租戶隔離
        conv = await self._conv_repo.find_by_id(query.conversation_id)
        if conv is None:
            raise EntityNotFoundError(
                entity_type="Conversation",
                entity_id=query.conversation_id,
            )
        if query.role != "system_admin" and conv.tenant_id != query.tenant_id:
            raise EntityNotFoundError(
                entity_type="Conversation",
                entity_id=query.conversation_id,
            )

        # 2. JOIN messages + bots + agent_execution_traces 取 usage + 名稱 + 來源
        session: AsyncSession = self._session_factory()
        try:
            stmt = (
                select(
                    UsageRecordModel.model,
                    UsageRecordModel.request_type,
                    UsageRecordModel.kb_id,
                    KnowledgeBaseModel.name.label("kb_name"),
                    UsageRecordModel.bot_id,
                    BotModel.name.label("bot_name"),
                    AgentExecutionTraceModel.source.label("channel_source"),
                    func.sum(UsageRecordModel.input_tokens).label("input_tokens"),
                    func.sum(UsageRecordModel.output_tokens).label("output_tokens"),
                    func.sum(UsageRecordModel.cache_read_tokens).label(
                        "cache_read_tokens"
                    ),
                    func.sum(UsageRecordModel.cache_creation_tokens).label(
                        "cache_creation_tokens"
                    ),
                    func.sum(UsageRecordModel.estimated_cost).label("estimated_cost"),
                    func.count().label("message_count"),
                )
                .join(
                    MessageModel,
                    UsageRecordModel.message_id == MessageModel.id,
                )
                .outerjoin(
                    KnowledgeBaseModel,
                    UsageRecordModel.kb_id == KnowledgeBaseModel.id,
                )
                .outerjoin(
                    BotModel,
                    UsageRecordModel.bot_id == BotModel.id,
                )
                .outerjoin(
                    AgentExecutionTraceModel,
                    UsageRecordModel.message_id
                    == AgentExecutionTraceModel.message_id,
                )
                .where(MessageModel.conversation_id == query.conversation_id)
                .group_by(
                    UsageRecordModel.model,
                    UsageRecordModel.request_type,
                    UsageRecordModel.kb_id,
                    KnowledgeBaseModel.name,
                    UsageRecordModel.bot_id,
                    BotModel.name,
                    AgentExecutionTraceModel.source,
                )
                .order_by(
                    func.sum(UsageRecordModel.estimated_cost).desc()
                )
            )
            rows = (await session.execute(stmt)).all()
        finally:
            await session.close()

        by_request_type: list[dict[str, Any]] = []
        totals = ConversationTokenUsageTotals()
        for r in rows:
            item = {
                "model": r.model,
                "request_type": r.request_type,
                "kb_id": r.kb_id,
                "kb_name": r.kb_name,
                "bot_id": r.bot_id,
                "bot_name": r.bot_name,
                "channel_source": r.channel_source,
                "input_tokens": int(r.input_tokens or 0),
                "output_tokens": int(r.output_tokens or 0),
                "cache_read_tokens": int(r.cache_read_tokens or 0),
                "cache_creation_tokens": int(r.cache_creation_tokens or 0),
                "estimated_cost": float(r.estimated_cost or 0),
                "message_count": int(r.message_count or 0),
            }
            by_request_type.append(item)
            totals.input_tokens += item["input_tokens"]
            totals.output_tokens += item["output_tokens"]
            totals.cache_read_tokens += item["cache_read_tokens"]
            totals.cache_creation_tokens += item["cache_creation_tokens"]
            totals.estimated_cost += item["estimated_cost"]
            totals.message_count += item["message_count"]

        return ConversationTokenUsageResult(
            conversation_id=query.conversation_id,
            totals=totals,
            by_request_type=by_request_type,
        )
