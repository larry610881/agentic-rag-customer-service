import asyncio
import time

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
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
from src.domain.rag.services import EmbeddingService, VectorStore
from src.domain.rag.value_objects import TokenUsage
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


async def _update_progress(task_id: str, progress: int) -> None:
    """Update task progress using independent session (best-effort)."""
    try:
        from src.infrastructure.db.engine import async_session_factory
        from src.infrastructure.db.models.processing_task_model import (
            ProcessingTaskModel,
        )
        from sqlalchemy import update

        async with async_session_factory() as session:
            await session.execute(
                update(ProcessingTaskModel)
                .where(ProcessingTaskModel.id == task_id)
                .values(progress=progress)
            )
            await session.commit()
    except Exception:
        pass


class ProcessDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        processing_task_repository: ProcessingTaskRepository,
        knowledge_base_repository: KnowledgeBaseRepository,
        text_splitter_service: TextSplitterService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        language_detection_service: LanguageDetectionService,
        file_parser_service: FileParserService,
        document_file_storage: DocumentFileStorageService,
        record_usage_use_case: RecordUsageUseCase | None = None,
    ) -> None:
        self._doc_repo = document_repository
        self._task_repo = processing_task_repository
        self._kb_repo = knowledge_base_repository
        self._splitter = text_splitter_service
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._language_detector = language_detection_service
        self._file_parser = file_parser_service
        self._file_storage = document_file_storage
        self._record_usage = record_usage_use_case

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

            # Load raw content: prefer file storage, fallback to DB BYTEA
            raw_content = None
            if document.storage_path:
                try:
                    raw_content = await self._file_storage.load(
                        document.storage_path
                    )
                except FileNotFoundError:
                    log.warning("document.file_storage.missing")
            if raw_content is None:
                raw_content = document.raw_content

            # Fetch KB to get ocr_mode
            kb = await self._kb_repo.find_by_id(document.kb_id)
            ocr_mode = kb.ocr_mode if kb else "general"

            # Parse raw content → text
            if raw_content:
                t0 = time.perf_counter()

                # PDF: use async path with progress callback
                if (
                    document.content_type == "application/pdf"
                    and hasattr(self._file_parser, "parse_pdf_async")
                ):
                    async def _on_progress(done: int, total: int) -> None:
                        pct = round(done / total * 70) if total else 0  # OCR = 0~70%
                        await _update_progress(task_id, pct)
                        log.info("ocr.progress", done=done, total=total)

                    content = await self._file_parser.parse_pdf_async(
                        raw_content,
                        ocr_mode=ocr_mode,
                        on_progress=_on_progress,
                        max_pages=2,  # TODO: 測試用，正式移除
                    )
                else:
                    content = await asyncio.to_thread(
                        self._file_parser.parse,
                        raw_content,
                        document.content_type,
                        ocr_mode,
                    )

                parse_ms = round((time.perf_counter() - t0) * 1000)
                log.info("document.parse.done", duration_ms=parse_ms)
                await self._doc_repo.update_content(document_id, content)

                # Record OCR token usage if applicable
                if self._record_usage and hasattr(self._file_parser, "last_input_tokens"):
                    in_tok = self._file_parser.last_input_tokens
                    out_tok = self._file_parser.last_output_tokens
                    if in_tok > 0 or out_tok > 0:
                        model = getattr(self._file_parser, "last_model", "claude-haiku-4-5-20251001")
                        await self._record_usage.execute(
                            tenant_id=document.tenant_id,
                            request_type="ocr",
                            usage=TokenUsage(
                                model=model,
                                input_tokens=in_tok,
                                output_tokens=out_tok,
                                total_tokens=in_tok + out_tok,
                            ),
                        )
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

            # 75% — chunks saved
            await _update_progress(task_id, 75)

            # Save chunks to DB
            t0 = time.perf_counter()
            await self._doc_repo.save_chunks(chunks)
            save_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.chunks.saved", chunk_count=len(chunks), duration_ms=save_ms)

            # 80% — embedding
            await _update_progress(task_id, 80)

            # Embed chunks
            t0 = time.perf_counter()
            texts = [c.content for c in chunks]
            vectors = await self._embedding.embed_texts(texts)
            embed_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.embed.done", vector_count=len(vectors), duration_ms=embed_ms)

            # 90% — upserting vectors
            await _update_progress(task_id, 90)

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
            # Re-raise so safe_background_task can write to Error Tracking
            raise
