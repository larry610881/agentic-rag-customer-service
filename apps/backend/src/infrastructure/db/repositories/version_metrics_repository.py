"""VersionMetricsRepository SQLAlchemy 實作（read model）

錨點：token_usage_records.config_version_id（Issue #54 §13.6 打標）。
品質訊號經 message_id join：messages(latency) / rag_evaluations(分數) /
feedback(評價)。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.prompt_gate.metrics import (
    VersionMetrics,
    VersionMetricsRepository,
)
from src.infrastructure.db.models.feedback_model import FeedbackModel
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.models.rag_eval_model import RAGEvalModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel


class SQLAlchemyVersionMetricsRepository(VersionMetricsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _usage_scope(self, tenant_id: str, version_id: str):
        return (
            UsageRecordModel.tenant_id == tenant_id,
            UsageRecordModel.config_version_id == version_id,
        )

    def _message_ids_subq(self, tenant_id: str, version_id: str):
        return (
            select(UsageRecordModel.message_id)
            .where(
                *self._usage_scope(tenant_id, version_id),
                UsageRecordModel.message_id.is_not(None),
            )
            .subquery()
        )

    async def get_metrics(
        self, tenant_id: str, version_id: str
    ) -> VersionMetrics:
        # 1. usage 聚合（訊息數 / tokens / 成本）
        usage_row = (
            await self._session.execute(
                select(
                    func.count(func.distinct(UsageRecordModel.message_id)),
                    func.coalesce(
                        func.sum(UsageRecordModel.input_tokens), 0
                    ),
                    func.coalesce(
                        func.sum(UsageRecordModel.output_tokens), 0
                    ),
                    func.coalesce(
                        func.sum(UsageRecordModel.estimated_cost), 0.0
                    ),
                ).where(*self._usage_scope(tenant_id, version_id))
            )
        ).one()

        msg_ids = self._message_ids_subq(tenant_id, version_id)

        # 2. 平均延遲（messages.latency_ms）
        avg_latency = (
            await self._session.execute(
                select(func.avg(MessageModel.latency_ms)).where(
                    MessageModel.id.in_(select(msg_ids.c.message_id)),
                    MessageModel.latency_ms.is_not(None),
                )
            )
        ).scalar_one()

        # 3. 線上 eval 平均分（by layer）
        eval_rows = (
            await self._session.execute(
                select(
                    RAGEvalModel.layer,
                    func.avg(RAGEvalModel.avg_score),
                )
                .where(
                    RAGEvalModel.message_id.in_(
                        select(msg_ids.c.message_id)
                    )
                )
                .group_by(RAGEvalModel.layer)
            )
        ).all()

        # 4. feedback（thumbs_up / thumbs_down）
        fb_rows = (
            await self._session.execute(
                select(FeedbackModel.rating, func.count())
                .where(
                    FeedbackModel.message_id.in_(
                        select(msg_ids.c.message_id)
                    )
                )
                .group_by(FeedbackModel.rating)
            )
        ).all()
        fb = dict(fb_rows)

        return VersionMetrics(
            version_id=version_id,
            message_count=usage_row[0] or 0,
            input_tokens=int(usage_row[1] or 0),
            output_tokens=int(usage_row[2] or 0),
            total_cost=round(float(usage_row[3] or 0.0), 6),
            avg_latency_ms=(
                round(float(avg_latency), 1)
                if avg_latency is not None
                else None
            ),
            eval_avg_by_layer={
                layer: round(float(score), 4)
                for layer, score in eval_rows
                if score is not None
            },
            feedback_up=fb.get("thumbs_up", 0),
            feedback_down=fb.get("thumbs_down", 0),
        )
