"""List KB Chunks Use Case — S-KB-Studio.1

KB-level chunk 分頁（跨文件），可選 category filter。驗 tenant 歸屬。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class ListKbChunksQuery:
    kb_id: str
    tenant_id: str
    page: int = 1
    page_size: int = 50
    category_id: str | None = None


@dataclass(frozen=True)
class ListKbChunksResult:
    items: list[Chunk]
    total: int
    page: int
    page_size: int


class ListKbChunksUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo

    async def execute(self, query: ListKbChunksQuery) -> ListKbChunksResult:
        kb = await self._kb_repo.find_by_id(query.kb_id)
        if kb is None or kb.tenant_id != query.tenant_id:
            raise EntityNotFoundError("kb", query.kb_id)

        items = await self._doc_repo.find_chunks_by_kb_paginated(
            query.kb_id,
            page=query.page,
            page_size=query.page_size,
            category_id=query.category_id,
        )
        total = await self._doc_repo.count_chunks_by_kb(
            query.kb_id, category_id=query.category_id
        )
        return ListKbChunksResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
