from dataclasses import dataclass

from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.services import ChunkQualityService


@dataclass
class ChunkPreviewItem:
    id: str
    content: str
    context_text: str
    chunk_index: int
    issues: list[str]
    page_number: int | None = None
    document_id: str = ""
    document_filename: str = ""


@dataclass
class ChunkPreviewResult:
    chunks: list[ChunkPreviewItem]
    total: int


class GetDocumentChunksUseCase:
    def __init__(self, document_repository: DocumentRepository) -> None:
        self._doc_repo = document_repository

    async def execute(
        self, document_id: str, limit: int = 20, offset: int = 0
    ) -> ChunkPreviewResult:
        # Try parent aggregation first — only aggregates if find_children returns real list
        try:
            children = await self._doc_repo.find_children(document_id)
        except Exception:
            children = None

        if isinstance(children, list) and len(children) > 0:
            all_items: list[ChunkPreviewItem] = []
            children_sorted = sorted(children, key=lambda c: c.page_number or 0)
            for child in children_sorted:
                child_chunks = await self._doc_repo.find_chunks_by_document_paginated(
                    child.id.value, limit=1000, offset=0
                )
                for chunk in child_chunks:
                    all_items.append(
                        _to_item(chunk, page_number=child.page_number, document_id=child.id.value, document_filename=child.filename)
                    )
            total = len(all_items)
            paged = all_items[offset : offset + limit]
            return ChunkPreviewResult(chunks=paged, total=total)

        # Regular document: just return its own chunks
        chunks = await self._doc_repo.find_chunks_by_document_paginated(
            document_id, limit=limit, offset=offset
        )
        total = await self._doc_repo.count_chunks_by_document(document_id)
        # Try to fetch doc metadata (page_number, filename) — optional
        page_number = None
        filename = ""
        try:
            doc = await self._doc_repo.find_by_id(document_id)
            if doc:
                page_number = getattr(doc, "page_number", None)
                filename = getattr(doc, "filename", "")
        except Exception:
            pass
        items = [
            _to_item(c, page_number=page_number, document_id=document_id, document_filename=filename)
            for c in chunks
        ]
        return ChunkPreviewResult(chunks=items, total=total)


def _to_item(chunk, page_number=None, document_id="", document_filename="") -> ChunkPreviewItem:
    issues: list[str] = []
    if len(chunk.content) < ChunkQualityService.SHORT_THRESHOLD:
        issues.append("too_short")
    if not chunk.content.rstrip().endswith(ChunkQualityService.SENTENCE_ENDINGS):
        issues.append("mid_sentence_break")
    return ChunkPreviewItem(
        id=chunk.id.value,
        content=chunk.content,
        context_text=chunk.context_text,
        chunk_index=chunk.chunk_index,
        issues=issues,
        page_number=page_number,
        document_id=document_id,
        document_filename=document_filename,
    )
