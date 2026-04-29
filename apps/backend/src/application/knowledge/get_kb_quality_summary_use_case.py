"""Get KB Quality Summary Use Case — S-KB-Studio.1

KB-level quality 聚合（低分 chunk 數、平均聚合度）。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)


@dataclass(frozen=True)
class GetKbQualitySummaryQuery:
    kb_id: str
    tenant_id: str


@dataclass
class KbQualitySummary:
    total_chunks: int
    low_quality_count: int  # quality_flag != None（含 too_short / incomplete）
    avg_cohesion_score: float  # 0-1 之間；目前用 1 - (low/total)


class GetKbQualitySummaryUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo

    async def execute(
        self, query: GetKbQualitySummaryQuery
    ) -> KbQualitySummary:
        from src.application.knowledge._admin_kb_check import ensure_kb_accessible
        await ensure_kb_accessible(self._kb_repo, query.kb_id, query.tenant_id)

        total = await self._doc_repo.count_chunks_by_kb(query.kb_id)
        # 先用粗估：掃第一頁 chunks 計 quality_flag（完整統計等 Day 2 加專用 SQL）
        sample = await self._doc_repo.find_chunks_by_kb_paginated(
            query.kb_id, page=1, page_size=min(total, 500)
        )
        low = sum(1 for c in sample if c.quality_flag)
        # 粗估聚合度 = 1 - low_ratio
        avg_cohesion = 1.0 - (low / len(sample)) if sample else 0.0
        return KbQualitySummary(
            total_chunks=total,
            low_quality_count=low,
            avg_cohesion_score=round(avg_cohesion, 4),
        )
