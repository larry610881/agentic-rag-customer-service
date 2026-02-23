from src.domain.knowledge.repository import (
    ChunkRepository,
    DocumentRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import TextSplitterService
from src.domain.rag.services import EmbeddingService, VectorStore


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
        try:
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

            # Update doc → processing
            await self._doc_repo.update_status(
                document_id, "processing"
            )

            # Split text into chunks
            chunks = self._splitter.split(
                document.content,
                document_id,
                document.tenant_id,
            )

            # Save chunks to DB
            await self._chunk_repo.save_batch(chunks)

            # Embed chunks
            texts = [c.content for c in chunks]
            vectors = await self._embedding.embed_texts(texts)

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
                }
                for c in chunks
            ]
            await self._vector_store.upsert(
                collection, chunk_ids, vectors, payloads
            )

            # Update doc → processed
            await self._doc_repo.update_status(
                document_id, "processed", chunk_count=len(chunks)
            )

            # Update task → completed
            await self._task_repo.update_status(
                task_id, "completed", progress=100
            )

        except Exception as e:
            # Update task → failed
            await self._task_repo.update_status(
                task_id,
                "failed",
                error_message=str(e),
            )
