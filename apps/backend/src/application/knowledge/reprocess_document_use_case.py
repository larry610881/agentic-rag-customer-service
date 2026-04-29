import asyncio

from src.domain.knowledge.entity import ProcessingTask
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
from src.domain.knowledge.value_objects import ProcessingTaskId
from src.domain.rag.services import EmbeddingService, VectorStore
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ReprocessDocumentUseCase:
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
        # Optional — 與 process_document feature parity（child rename 用）
        record_usage_use_case=None,
        tenant_repository=None,
        chunk_context_service=None,  # for api_key_resolver in child rename
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
        self._tenant_repo = tenant_repository
        self._context_service = chunk_context_service

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

        # 同步把 child + parent 都標 processing（在 200/202 返回前）
        # → frontend 拿到的 snapshot 立刻就是 processing → polling 啟動 → 看得到進度條
        # 否則 background task 還沒跑 frontend invalidate 拿到的是 failed → 不 polling
        try:
            await self._doc_repo.update_status(document_id, "processing")
            doc = await self._doc_repo.find_by_id(document_id)
            if doc and doc.parent_id:
                await self._doc_repo.update_status(doc.parent_id, "processing")
        except Exception:
            logger.warning(
                "begin_reprocess.status_update_failed",
                document_id=document_id,
                exc_info=True,
            )
        return task

    async def execute(  # noqa: C901
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

            # Delete old vectors from Milvus
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

            # Fetch KB to get ocr_mode
            kb = await self._kb_repo.find_by_id(document.kb_id)
            ocr_mode = kb.ocr_mode if kb else "general"

            # Re-parse from raw_content if available, else fallback to existing content
            if raw_content:
                # PNG/image (PDF child pages): file_parser.parse 不支援 image/*
                if document.content_type.startswith("image/") and hasattr(
                    self._file_parser, "_ocr"
                ):
                    ocr_engine = self._file_parser._ocr
                    from src.infrastructure.file_parser.ocr_engines import (
                        claude_vision_ocr,
                    )
                    prompts = claude_vision_ocr.OCR_PROMPTS
                    prompt = prompts.get(ocr_mode, prompts.get("general", ""))
                    content = await ocr_engine.ocr_page(
                        raw_content, prompt=prompt
                    )
                    log.info(
                        "document.reparse.ocr_done",
                        content_type=document.content_type,
                    )
                # PDF：用 async 路徑（避免阻塞 + 支援大檔逐頁進度）
                elif (
                    document.content_type == "application/pdf"
                    and hasattr(self._file_parser, "parse_pdf_async")
                ):
                    content = await self._file_parser.parse_pdf_async(
                        raw_content,
                        ocr_mode=ocr_mode,
                    )
                    log.info("document.reparse.pdf_done")
                # 其他（txt/csv/json/xml/html/docx/xlsx 等）走 sync parser
                else:
                    content = await asyncio.to_thread(
                        self._file_parser.parse,
                        raw_content,
                        document.content_type,
                        ocr_mode,
                    )
                    log.info("document.reparse.done")
                await self._doc_repo.update_content(document_id, content)
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
                if document.parent_id:
                    from src.application.knowledge._parent_aggregation import (
                        aggregate_parent_status_if_complete,
                    )
                    await aggregate_parent_status_if_complete(
                        self._doc_repo, document.parent_id, log
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
                if document.parent_id:
                    from src.application.knowledge._parent_aggregation import (
                        aggregate_parent_status_if_complete,
                    )
                    await aggregate_parent_status_if_complete(
                        self._doc_repo, document.parent_id, log
                    )
                return

            # Save new chunks
            await self._doc_repo.save_chunks(chunks)

            # Embed and upsert vectors
            texts = [c.content for c in chunks]
            vectors = await self._embedding.embed_texts(texts)

            vector_size = len(vectors[0]) if vectors else 3072
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

            # PDF 子頁 LLM rename — 與 process_document 對齊（共用 helper）
            # 之前 reprocess 沒呼叫 → 子頁 reprocess 完仍顯示「第 N 頁」沒主題
            if document.parent_id and document.page_number:
                from src.application.knowledge._child_rename import (
                    rename_child_page_if_pdf,
                )
                await rename_child_page_if_pdf(
                    document_id=document_id,
                    page_number=document.page_number,
                    content=content,
                    kb=kb,
                    tenant_id=document.tenant_id,
                    doc_repo=self._doc_repo,
                    tenant_repo=self._tenant_repo,
                    record_usage=self._record_usage,
                    context_service=self._context_service,
                    log=log,
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

            # 子頁完成 → 檢查父 doc 是否該重新聚合 status / quality
            if document.parent_id:
                from src.application.knowledge._parent_aggregation import (
                    aggregate_parent_status_if_complete,
                )
                await aggregate_parent_status_if_complete(
                    self._doc_repo, document.parent_id, log
                )

        except Exception as e:
            log.exception("document.reprocess.failed", error=str(e))
            await self._doc_repo.update_status(document_id, "failed")
            await self._task_repo.update_status(
                task_id, "failed", error_message=str(e)
            )
            # 子頁失敗也要 trigger 父 doc 聚合（其他兄弟全 OK 時父應 processed）
            if document.parent_id:
                from src.application.knowledge._parent_aggregation import (
                    aggregate_parent_status_if_complete,
                )
                await aggregate_parent_status_if_complete(
                    self._doc_repo, document.parent_id, log
                )
            # Re-raise so safe_background_task can write to Error Tracking
            raise
