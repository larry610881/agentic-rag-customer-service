from dataclasses import dataclass

from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.knowledge.repository import ChunkRepository, DocumentRepository


@dataclass
class DocumentQualityStat:
    document_id: str
    filename: str
    quality_score: float
    negative_feedback_count: int


class GetDocumentQualityStatsUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        feedback_repository: FeedbackRepository,
    ) -> None:
        self._doc_repo = document_repository
        self._chunk_repo = chunk_repository
        self._feedback_repo = feedback_repository

    async def execute(
        self, kb_id: str, tenant_id: str, days: int = 30
    ) -> list[DocumentQualityStat]:
        # 1. Get all documents in KB
        documents = await self._doc_repo.find_all_by_kb(kb_id)
        if not documents:
            return []

        doc_ids = [d.id.value for d in documents]
        doc_map = {d.id.value: d for d in documents}

        # 2. Get chunk_id → document_id mapping (JOIN instead of IN clause)
        chunk_to_doc = await self._chunk_repo.find_chunk_ids_by_kb(kb_id)
        # Invert: chunk_id → document_id
        chunk_id_to_doc_id: dict[str, str] = {}
        for doc_id, chunk_ids in chunk_to_doc.items():
            for cid in chunk_ids:
                chunk_id_to_doc_id[cid] = doc_id

        # 3. Get negative feedback with retrieved_chunks context
        negative_records = await self._feedback_repo.get_negative_with_context(
            tenant_id, days=days, limit=1000, offset=0
        )

        # 4. Count negative feedback per document
        neg_count: dict[str, int] = dict.fromkeys(doc_ids, 0)
        for record in negative_records:
            for chunk_info in record.retrieved_chunks:
                chunk_id = chunk_info.get("chunk_id", "")
                matched_doc_id = chunk_id_to_doc_id.get(chunk_id)
                if matched_doc_id and matched_doc_id in neg_count:
                    neg_count[matched_doc_id] += 1
                    break  # Count once per feedback per document

        # 5. Build result
        return [
            DocumentQualityStat(
                document_id=did,
                filename=doc_map[did].filename,
                quality_score=doc_map[did].quality_score,
                negative_feedback_count=neg_count[did],
            )
            for did in doc_ids
        ]
