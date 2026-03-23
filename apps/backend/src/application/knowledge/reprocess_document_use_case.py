import asyncio

from src.domain.knowledge.entity import ProcessingTask
from src.domain.knowledge.repository import (
    DocumentRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import (
    ChunkDeduplicationService,
    ChunkFilterService,
    ChunkQualityService,
    DocumentFileStorageService,
    FileParserService,
    LanguageDetectionService,
    TextPreprocessor,
    TextSplitterService,
)
from src.domain.knowledge.value_objects import ProcessingTaskId
from src.domain.rag.services import EmbeddingService, VectorStore
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ReprocessDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        processing_task_repository: ProcessingTaskRepository,
        text_splitter_service: TextSplitterService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        language_detection_service: LanguageDetectionService,
        file_parser_service: FileParserService,
        document_file_storage: DocumentFileStorageService,
    ) -> None:
        self._doc_repo = document_repository
        self._task_repo = processing_task_repository
        self._splitter = text_splitter_service
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._language_detector = language_detection_service
        self._file_parser = file_parser_service
        self._file_storage = document_file_storage

    async def begin_reprocess(
        self, document_id: str, tenant_id: str
    ) -> ProcessingTask:
        task = ProcessingTask(
            id=ProcessingTaskId(),
            document_id=document_id,
            tenant_id=tenant_id,
            status="pending",
        )
        await self._task_repo.save(task)
        return task

    async def execute(
        self,
        document_id: str,
        task_id: str,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunk_strategy: str | None = None,
    ) -> None:
        log = logger.bind(document_id=document_id, task_id=task_id)
        log.info("document.reprocess.start")

        document = await self._doc_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Document '{document_id}' not found")

        # Mark as processing
        await self._doc_repo.update_status(document_id, "processing")
        await self._task_repo.update_status(task_id, "processing", progress=0)

        try:
            # Delete old chunks from DB
            await self._doc_repo.delete_chunks_by_document(document_id)

            # Delete old vectors from Qdrant
            collection = f"kb_{document.kb_id}"
            await self._vector_store.delete(
                collection, {"document_id": document_id}
            )

            # Load raw content: prefer file storage, fallback to DB BYTEA
            raw_content = None
            if document.storage_path:
                try:
                    raw_content = await self._file_storage.load(
                        document.storage_path
                    )
                except FileNotFoundError:
                    pass
            if raw_content is None:
                raw_content = document.raw_content

            # Re-parse from raw_content if available, else fallback to existing content
            if raw_content:
                content = await asyncio.to_thread(
                    self._file_parser.parse,
                    raw_content,
                    document.content_type,
                )
                await self._doc_repo.update_content(document_id, content)
                log.info("document.reparse.done")
            else:
                content = document.content

            # Pre-process: normalize + boilerplate removal
            preprocessed = TextPreprocessor.preprocess(
                content, document.content_type
            )

            # Detect language
            language = self._language_detector.detect(preprocessed)
            log.info("document.language.detected", language=language)

            # Re-split with (potentially overridden) parameters
            chunks = self._splitter.split(
                preprocessed,
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
                await self._task_repo.update_status(
                    task_id, "completed", progress=100
                )
                return

            # Calculate quality (before filtering)
            quality = ChunkQualityService.calculate(chunks)
            await self._doc_repo.update_quality(
                document_id,
                quality_score=quality.score,
                avg_chunk_length=quality.avg_chunk_length,
                min_chunk_length=quality.min_chunk_length,
                max_chunk_length=quality.max_chunk_length,
                quality_issues=list(quality.issues),
            )

            # Filter low-quality chunks
            filter_result = ChunkFilterService.filter(chunks)
            if filter_result.rejected_count:
                log.info(
                    "document.chunks.filtered",
                    rejected=filter_result.rejected_count,
                )
            chunks = filter_result.accepted

            # Deduplicate
            pre_dedup = len(chunks)
            chunks = ChunkDeduplicationService.deduplicate(chunks)
            if len(chunks) < pre_dedup:
                log.info(
                    "document.chunks.deduplicated",
                    before=pre_dedup,
                    after=len(chunks),
                )

            # Empty after filtering/dedup
            if not chunks:
                await self._doc_repo.update_status(
                    document_id, "processed", chunk_count=0
                )
                await self._task_repo.update_status(
                    task_id, "completed", progress=100
                )
                return

            # Save new chunks
            await self._doc_repo.save_chunks(chunks)

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
                    "language": language,
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
            await self._task_repo.update_status(
                task_id, "completed", progress=100
            )
            log.info(
                "document.reprocess.done",
                quality_score=quality.score,
                chunk_count=len(chunks),
            )

        except Exception as e:
            log.exception("document.reprocess.failed", error=str(e))
            await self._doc_repo.update_status(document_id, "failed")
            await self._task_repo.update_status(
                task_id, "failed", error_message=str(e)
            )
            # Re-raise so safe_background_task can write to Error Tracking
            raise
