from dataclasses import dataclass

from src.domain.knowledge.repository import ChunkRepository
from src.domain.knowledge.services import ChunkQualityService


@dataclass
class ChunkPreviewItem:
    id: str
    content: str
    chunk_index: int
    issues: list[str]


@dataclass
class ChunkPreviewResult:
    chunks: list[ChunkPreviewItem]
    total: int


class GetDocumentChunksUseCase:
    def __init__(self, chunk_repository: ChunkRepository) -> None:
        self._chunk_repo = chunk_repository

    async def execute(
        self, document_id: str, limit: int = 20, offset: int = 0
    ) -> ChunkPreviewResult:
        chunks = await self._chunk_repo.find_by_document_paginated(
            document_id, limit=limit, offset=offset
        )
        total = await self._chunk_repo.count_by_document(document_id)

        items: list[ChunkPreviewItem] = []
        for chunk in chunks:
            issues: list[str] = []
            if len(chunk.content) < ChunkQualityService.SHORT_THRESHOLD:
                issues.append("too_short")
            if not chunk.content.rstrip().endswith(
                ChunkQualityService.SENTENCE_ENDINGS
            ):
                issues.append("mid_sentence_break")
            items.append(
                ChunkPreviewItem(
                    id=chunk.id.value,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    issues=issues,
                )
            )

        return ChunkPreviewResult(chunks=items, total=total)
