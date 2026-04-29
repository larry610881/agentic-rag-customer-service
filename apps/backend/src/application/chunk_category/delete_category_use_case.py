"""Delete Category Use Case — S-KB-Studio.1"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.domain.knowledge.repository import (
    ChunkCategoryRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DeleteCategoryCommand:
    kb_id: str
    category_id: str
    tenant_id: str
    actor: str = ""


class DeleteCategoryUseCase:
    def __init__(
        self,
        category_repo: ChunkCategoryRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self._repo = category_repo
        self._kb_repo = kb_repo

    async def execute(self, command: DeleteCategoryCommand) -> int:
        """回傳受影響的 chunk 數。"""
        from src.application.knowledge._admin_kb_check import ensure_kb_accessible
        await ensure_kb_accessible(
            self._kb_repo, command.kb_id, command.tenant_id
        )

        category = await self._repo.find_by_id(command.category_id)
        if category is None or category.kb_id != command.kb_id:
            raise EntityNotFoundError("category", command.category_id)

        chunk_count = category.chunk_count
        await self._repo.delete_by_id(command.category_id)
        logger.info(
            "kb_studio.category.delete",
            cat_id=command.category_id,
            kb_id=command.kb_id,
            chunk_count=chunk_count,
            actor=command.actor,
        )
        return chunk_count
