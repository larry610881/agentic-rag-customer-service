from src.domain.knowledge.repository import (
    ChunkRepository,
    DocumentRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import ChunkQualityService, TextSplitterService
from src.domain.rag.services import EmbeddingService, VectorStore
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ReprocessDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        processing_task_repository: ProcessingTaskRepository,
        text_splitter_service: TextSplitterService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._doc_repo = document_repository
        self._chunk_repo = chunk_repository
        self._task_repo = processing_task_repository
        self._splitter = text_splitter_service
        self._embedding = embedding_service
        self._vector_store = vector_store

    async def execute(
        self,
        document_id: str,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunk_strategy: str | None = None,
    ) -> None:
        log = logger.bind(document_id=document_id)
        log.info("document.reprocess.start")

        document = await self._doc_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Document '{document_id}' not found")

        # Mark as processing
        await self._doc_repo.update_status(document_id, "processing")

        try:
            # Delete old chunks from DB
            await self._chunk_repo.delete_by_document(document_id)

            # Delete old vectors from Qdrant
            collection = f"kb_{document.kb_id}"
            await self._vector_store.delete(
                collection, {"document_id": document_id}
            )

            # Re-split with (potentially overridden) parameters
            chunks = self._splitter.split(
                document.content,
                document_id,
                document.tenant_id,
                content_type=document.content_type,
            )
            log.info("document.reprocess.split", chunk_count=len(chunks))

            if not chunks:
                await self._doc_repo.update_status(
                    document_id, "processed", chunk_count=0
                )
                await self._doc_repo.update_quality(
                    document_id, 0.0, 0, 0, 0, []
                )
                return

            # Save new chunks
            await self._chunk_repo.save_batch(chunks)

            # Calculate quality
            quality = ChunkQualityService.calculate(chunks)
            await self._doc_repo.update_quality(
                document_id,
                quality_score=quality.score,
                avg_chunk_length=quality.avg_chunk_length,
                min_chunk_length=quality.min_chunk_length,
                max_chunk_length=quality.max_chunk_length,
                quality_issues=list(quality.issues),
            )

            # Embed and upsert vectors
            texts = [c.content for c in chunks]
            vectors = await self._embedding.embed_texts(texts)

            vector_size = len(vectors[0]) if vectors else 1536
            await self._vector_store.ensure_collection(collection, vector_size)

            chunk_ids = [c.id.value for c in chunks]
            payloads = [
                {
                    "tenant_id": document.tenant_id,
                    "document_id": document_id,
                    "content": c.content,
                    "chunk_index": c.chunk_index,
                    "content_type": document.content_type,
                }
                for c in chunks
            ]
            await self._vector_store.upsert(
                collection, chunk_ids, vectors, payloads
            )

            # Mark as processed
            await self._doc_repo.update_status(
                document_id, "processed", chunk_count=len(chunks)
            )
            log.info(
                "document.reprocess.done",
                quality_score=quality.score,
                chunk_count=len(chunks),
            )

        except Exception as e:
            log.exception("document.reprocess.failed", error=str(e))
            await self._doc_repo.update_status(document_id, "failed")
            raise
