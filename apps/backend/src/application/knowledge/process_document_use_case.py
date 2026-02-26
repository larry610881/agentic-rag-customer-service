from src.domain.knowledge.repository import (
    ChunkRepository,
    DocumentRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import TextSplitterService
from src.domain.rag.services import EmbeddingService, VectorStore
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProcessDocumentUseCase:
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
        self, document_id: str, task_id: str
    ) -> None:
        log = logger.bind(document_id=document_id, task_id=task_id)
        try:
            log.info("document.process.start")

            # Update task → processing
            await self._task_repo.update_status(
                task_id, "processing", progress=0
            )

            # Fetch document
            document = await self._doc_repo.find_by_id(document_id)
            if document is None:
                raise ValueError(
                    f"Document '{document_id}' not found"
                )

            log = log.bind(tenant_id=document.tenant_id, kb_id=document.kb_id)

            # Update doc → processing
            await self._doc_repo.update_status(
                document_id, "processing"
            )

            # Split text into chunks
            chunks = self._splitter.split(
                document.content,
                document_id,
                document.tenant_id,
                content_type=document.content_type,
            )
            log.info("document.split.done", chunk_count=len(chunks))

            # Empty chunks early return
            if not chunks:
                log.warning("document.process.empty")
                await self._doc_repo.update_status(
                    document_id, "processed", chunk_count=0
                )
                await self._task_repo.update_status(task_id, "completed", progress=100)
                return

            # Save chunks to DB
            await self._chunk_repo.save_batch(chunks)

            # Embed chunks
            texts = [c.content for c in chunks]
            vectors = await self._embedding.embed_texts(texts)
            log.info("document.embed.done", vector_count=len(vectors))

            # Ensure Qdrant collection exists
            collection = f"kb_{document.kb_id}"
            vector_size = len(vectors[0]) if vectors else 1536
            await self._vector_store.ensure_collection(
                collection, vector_size
            )

            # Upsert vectors with tenant_id in payload
            chunk_ids = [c.id.value for c in chunks]
            payloads = [
                {
                    "tenant_id": document.tenant_id,
                    "document_id": document_id,
                    "content": c.content,
                    "chunk_index": c.chunk_index,
                    "content_type": document.content_type,
                    **{
                        k: v
                        for k, v in c.metadata.items()
                        if k not in ("document_id", "tenant_id")
                    },
                }
                for c in chunks
            ]
            await self._vector_store.upsert(
                collection, chunk_ids, vectors, payloads
            )
            log.info(
                "document.upsert.done",
                collection=collection,
                point_count=len(chunk_ids),
            )

            # Update doc → processed
            await self._doc_repo.update_status(
                document_id, "processed", chunk_count=len(chunks)
            )

            # Update task → completed
            await self._task_repo.update_status(
                task_id, "completed", progress=100
            )

            log.info("document.process.done")

        except Exception as e:
            log.exception("document.process.failed", error=str(e))
            # Update task → failed
            await self._task_repo.update_status(
                task_id,
                "failed",
                error_message=str(e),
            )
            # Update document → failed
            try:
                await self._doc_repo.update_status(document_id, "failed")
            except Exception:
                log.exception("document.status_update.failed")
