import asyncio
import time

from src.domain.knowledge.repository import (
    DocumentRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import (
    ChunkDeduplicationService,
    ChunkFilterService,
    ChunkQualityService,
    FileParserService,
    LanguageDetectionService,
    TextPreprocessor,
    TextSplitterService,
)
from src.domain.rag.services import EmbeddingService, VectorStore
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProcessDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        processing_task_repository: ProcessingTaskRepository,
        text_splitter_service: TextSplitterService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        language_detection_service: LanguageDetectionService,
        file_parser_service: FileParserService,
    ) -> None:
        self._doc_repo = document_repository
        self._task_repo = processing_task_repository
        self._splitter = text_splitter_service
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._language_detector = language_detection_service
        self._file_parser = file_parser_service

    async def execute(
        self, document_id: str, task_id: str
    ) -> None:
        log = logger.bind(document_id=document_id, task_id=task_id)
        try:
            t_total = time.perf_counter()
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

            log = log.bind(
                tenant_id=document.tenant_id,
                kb_id=document.kb_id,
                filename=document.filename,
            )

            # Update doc → processing
            await self._doc_repo.update_status(
                document_id, "processing"
            )

            # Parse raw content → text (moved from upload for async processing)
            if document.raw_content:
                t0 = time.perf_counter()
                content = await asyncio.to_thread(
                    self._file_parser.parse,
                    document.raw_content,
                    document.content_type,
                )
                parse_ms = round((time.perf_counter() - t0) * 1000)
                log.info("document.parse.done", duration_ms=parse_ms)
                await self._doc_repo.update_content(document_id, content)
            else:
                # Fallback for legacy documents without raw_content
                content = document.content
                parse_ms = 0

            # Pre-process: normalize + boilerplate removal
            t0 = time.perf_counter()
            preprocessed = TextPreprocessor.preprocess(
                content, document.content_type
            )

            # Detect language
            language = self._language_detector.detect(preprocessed)
            preprocess_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.preprocess.done", language=language, duration_ms=preprocess_ms)

            # Split text into chunks
            t0 = time.perf_counter()
            chunks = self._splitter.split(
                preprocessed,
                document_id,
                document.tenant_id,
                content_type=document.content_type,
            )
            split_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.split.done", chunk_count=len(chunks), duration_ms=split_ms)

            # Empty chunks early return
            if not chunks:
                log.warning("document.process.empty")
                await self._doc_repo.update_status(
                    document_id, "processed", chunk_count=0
                )
                await self._task_repo.update_status(task_id, "completed", progress=100)
                return

            # Calculate chunk quality (before filtering, for full picture)
            quality = ChunkQualityService.calculate(chunks)
            await self._doc_repo.update_quality(
                document_id,
                quality_score=quality.score,
                avg_chunk_length=quality.avg_chunk_length,
                min_chunk_length=quality.min_chunk_length,
                max_chunk_length=quality.max_chunk_length,
                quality_issues=list(quality.issues),
            )
            log.info(
                "document.quality.calculated",
                quality_score=quality.score,
                issues=quality.issues,
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
                log.warning("document.process.empty_after_filter")
                await self._doc_repo.update_status(
                    document_id, "processed", chunk_count=0
                )
                await self._task_repo.update_status(task_id, "completed", progress=100)
                return

            # Save chunks to DB
            t0 = time.perf_counter()
            await self._doc_repo.save_chunks(chunks)
            save_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.chunks.saved", chunk_count=len(chunks), duration_ms=save_ms)

            # Embed chunks
            t0 = time.perf_counter()
            texts = [c.content for c in chunks]
            vectors = await self._embedding.embed_texts(texts)
            embed_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.embed.done", vector_count=len(vectors), duration_ms=embed_ms)

            # Ensure Qdrant collection exists
            collection = f"kb_{document.kb_id}"
            vector_size = len(vectors[0]) if vectors else 1536
            await self._vector_store.ensure_collection(
                collection, vector_size
            )

            # Upsert vectors with tenant_id in payload
            t0 = time.perf_counter()
            chunk_ids = [c.id.value for c in chunks]
            payloads = [
                {
                    "tenant_id": document.tenant_id,
                    "document_id": document_id,
                    "content": c.content,
                    "chunk_index": c.chunk_index,
                    "content_type": document.content_type,
                    "language": language,
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
            upsert_ms = round((time.perf_counter() - t0) * 1000)
            log.info(
                "document.upsert.done",
                collection=collection,
                point_count=len(chunk_ids),
                duration_ms=upsert_ms,
            )

            # Update doc → processed
            await self._doc_repo.update_status(
                document_id, "processed", chunk_count=len(chunks)
            )

            # Update task → completed
            await self._task_repo.update_status(
                task_id, "completed", progress=100
            )

            total_ms = round((time.perf_counter() - t_total) * 1000)
            log.info(
                "document.process.done",
                total_ms=total_ms,
                parse_ms=parse_ms,
                preprocess_ms=preprocess_ms,
                split_ms=split_ms,
                save_ms=save_ms,
                embed_ms=embed_ms,
                upsert_ms=upsert_ms,
                chunk_count=len(chunks),
            )

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
