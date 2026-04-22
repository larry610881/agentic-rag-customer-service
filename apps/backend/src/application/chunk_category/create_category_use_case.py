"""Create Category Use Case — S-KB-Studio.1"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import structlog

from src.domain.knowledge.entity import ChunkCategory
from src.domain.knowledge.repository import (
    ChunkCategoryRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CreateCategoryCommand:
    kb_id: str
    tenant_id: str
    name: str
    description: str | None = None
    actor: str = ""


class CreateCategoryUseCase:
    def __init__(
        self,
        category_repo: ChunkCategoryRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self._repo = category_repo
        self._kb_repo = kb_repo

    async def execute(self, command: CreateCategoryCommand) -> ChunkCategory:
        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None or kb.tenant_id != command.tenant_id:
            raise EntityNotFoundError("kb", command.kb_id)
        if not command.name.strip():
            raise ValueError("name must not be empty")

        category = ChunkCategory(
            id=str(uuid4()),
            kb_id=command.kb_id,
            tenant_id=command.tenant_id,
            name=command.name,
            description=command.description,
            chunk_count=0,
        )
        await self._repo.save(category)
        logger.info(
            "kb_studio.category.create",
            cat_id=category.id,
            kb_id=command.kb_id,
            name=command.name,
            actor=command.actor,
        )
        return category
