import asyncio
import time

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import (
    ChunkContextService,
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
from src.domain.tenant.repository import TenantRepository
from src.domain.usage.category import UsageCategory
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


async def _update_progress(task_id: str, progress: int) -> None:
    """Update task progress using independent session (best-effort)."""
    try:
        from sqlalchemy import update

        from src.infrastructure.db.engine import async_session_factory
        from src.infrastructure.db.models.processing_task_model import (
            ProcessingTaskModel,
        )

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
        chunk_context_service: ChunkContextService | None = None,
        tenant_repository: TenantRepository | None = None,
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
        self._context_service = chunk_context_service
        self._tenant_repo = tenant_repository

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

            # ── Parse raw content → text ──
            # Determine if this is a long-running OCR path
            needs_ocr = (
                raw_content
                and (
                    document.content_type.startswith("image/")
                    or (document.content_type == "application/pdf" and ocr_mode == "catalog")
                )
            )

            # OCR is long-running (10s+/page). Close session before OCR
            # to return the connection to the pool. Non-OCR (JSON/TXT/CSV)
            # is fast and doesn't need session close.
            if needs_ocr and hasattr(self._doc_repo, '_session'):
                try:
                    await self._doc_repo._session.close()
                except Exception:
                    pass

            if raw_content:
                t0 = time.perf_counter()

                # PNG/image: single page OCR (child of split PDF)
                if document.content_type.startswith("image/") and hasattr(self._file_parser, "_ocr"):
                    ocr_engine = self._file_parser._ocr
                    from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
                        OCR_PROMPTS,
                    )
                    prompt = OCR_PROMPTS.get(ocr_mode, OCR_PROMPTS.get("general", ""))
                    content = await ocr_engine.ocr_page(raw_content, prompt=prompt)
                    await _update_progress(task_id, 70)

                # PDF: use async path with progress callback (no DB held)
                elif (
                    document.content_type == "application/pdf"
                    and hasattr(self._file_parser, "parse_pdf_async")
                ):
                    async def _on_progress(done: int, total: int) -> None:
                        pct = round(done / total * 70) if total else 0
                        await _update_progress(task_id, pct)
                        log.info("ocr.progress", done=done, total=total)

                    content = await self._file_parser.parse_pdf_async(
                        raw_content,
                        ocr_mode=ocr_mode,
                        on_progress=_on_progress,
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

                # Refresh session after long OCR — old connection may be dead
                if needs_ocr and hasattr(self._doc_repo, '_session'):
                    try:
                        from src.infrastructure.db.engine import async_session_factory
                        new_session = async_session_factory()
                        self._doc_repo._session = new_session
                        self._task_repo._session = new_session
                        self._kb_repo._session = new_session
                    except Exception:
                        pass

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

            # ── Contextual Enrichment (Contextual Retrieval) ──
            # Resolve: KB setting → tenant default → skip
            context_model = getattr(kb, "context_model", "") if kb else ""
            if not context_model and self._tenant_repo:
                try:
                    tenant = await self._tenant_repo.find_by_id(document.tenant_id)
                    context_model = getattr(tenant, "default_context_model", "") if tenant else ""
                except Exception:
                    pass
            if self._context_service and context_model:
                # Close session before LLM calls (same pattern as OCR)
                if hasattr(self._doc_repo, '_session'):
                    try:
                        await self._doc_repo._session.close()
                    except Exception:
                        pass

                t0 = time.perf_counter()
                chunks = await self._context_service.generate_contexts(
                    content, chunks, model=context_model
                )
                ctx_ms = round((time.perf_counter() - t0) * 1000)
                ctx_count = sum(1 for c in chunks if c.context_text)
                log.info(
                    "document.context.done",
                    enriched=ctx_count,
                    total=len(chunks),
                    duration_ms=ctx_ms,
                )

                # Refresh session after LLM calls — must be done **before**
                # record_usage（否則 usage_repo._session 仍是已關閉的 session
                # → record_usage.save 沉默失敗，token 永遠寫不進 DB）。
                # S-LLM-Cache.1 fix：同步 refresh record_usage 的 inner repo session。
                if hasattr(self._doc_repo, '_session'):
                    try:
                        from src.infrastructure.db.engine import async_session_factory
                        new_session = async_session_factory()
                        self._doc_repo._session = new_session
                        self._task_repo._session = new_session
                        self._kb_repo._session = new_session
                        # 關鍵：record_usage 的 usage_repository 也綁同一個
                        # ContextVar session（已被 close 了），需顯式 refresh
                        if (
                            self._record_usage is not None
                            and hasattr(self._record_usage, "_repo")
                            and hasattr(self._record_usage._repo, "_session")
                        ):
                            self._record_usage._repo._session = new_session
                    except Exception:
                        pass

                # Token-Gov.0: 記錄 contextual retrieval token 用量
                # S-LLM-Cache.1: 加上 cache_read / cache_creation 欄位
                if self._record_usage and getattr(
                    self._context_service, "last_input_tokens", 0
                ) + getattr(
                    self._context_service, "last_output_tokens", 0
                ) > 0:
                    ctx_in = self._context_service.last_input_tokens
                    ctx_out = self._context_service.last_output_tokens
                    ctx_cache_read = getattr(
                        self._context_service, "last_cache_read_tokens", 0
                    )
                    ctx_cache_creation = getattr(
                        self._context_service, "last_cache_creation_tokens", 0
                    )
                    ctx_model = getattr(
                        self._context_service, "last_model", context_model
                    )
                    await self._record_usage.execute(
                        tenant_id=document.tenant_id,
                        request_type=UsageCategory.CONTEXTUAL_RETRIEVAL.value,
                        usage=TokenUsage(
                            model=ctx_model,
                            input_tokens=ctx_in,
                            output_tokens=ctx_out,
                            cache_read_tokens=ctx_cache_read,
                            cache_creation_tokens=ctx_cache_creation,
                        ),
                    )

                await _update_progress(task_id, 73)

            # 75% — chunks saved
            await _update_progress(task_id, 75)

            # Save chunks to DB
            t0 = time.perf_counter()
            await self._doc_repo.save_chunks(chunks)
            save_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.chunks.saved", chunk_count=len(chunks), duration_ms=save_ms)

            # 80% — embedding
            await _update_progress(task_id, 80)

            # Embed chunks (with context if available)
            t0 = time.perf_counter()
            texts = [
                f"{c.context_text}\n\n{c.content}" if c.context_text else c.content
                for c in chunks
            ]
            vectors = await self._embedding.embed_texts(texts)
            embed_ms = round((time.perf_counter() - t0) * 1000)
            log.info("document.embed.done", vector_count=len(vectors), duration_ms=embed_ms)

            # Record embedding token usage
            if self._record_usage and hasattr(self._embedding, "last_total_tokens"):
                embed_tokens = self._embedding.last_total_tokens
                if embed_tokens > 0:
                    embed_model = getattr(self._embedding, "_model", "text-embedding-3-large")
                    await self._record_usage.execute(
                        tenant_id=document.tenant_id,
                        request_type="embedding",
                        usage=TokenUsage(
                            model=embed_model,
                            input_tokens=embed_tokens,
                            output_tokens=0,
                        ),
                    )

            # 90% — upserting vectors
            await _update_progress(task_id, 90)

            # Ensure Milvus collection exists
            collection = f"kb_{document.kb_id}"
            vector_size = len(vectors[0]) if vectors else 3072
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

            # If child document (PDF page), generate semantic filename
            if document.parent_id and document.page_number:
                try:
                    await self._rename_child_page(
                        document_id,
                        document.page_number,
                        content,
                        kb,
                        log,
                        tenant_id=document.tenant_id,
                    )
                except Exception:
                    log.warning("child.rename_failed", exc_info=True)

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

            # If child document, check if all siblings done → update parent
            if document.parent_id:
                try:
                    status_counts = await self._doc_repo.count_children_by_status(document.parent_id)
                    total = sum(status_counts.values())
                    done = status_counts.get("processed", 0)
                    failed = status_counts.get("failed", 0)
                    if done + failed == total:
                        parent_status = "processed" if failed == 0 else "failed"
                        # Aggregate chunk counts + quality from all children
                        children = await self._doc_repo.find_children(document.parent_id)
                        total_chunks = sum(c.chunk_count for c in children)
                        # Average quality across children with chunks
                        children_with_chunks = [c for c in children if c.chunk_count > 0]
                        if children_with_chunks:
                            avg_quality = sum(c.quality_score for c in children_with_chunks) / len(children_with_chunks)
                            avg_chunk_len = sum(c.avg_chunk_length for c in children_with_chunks) // len(children_with_chunks)
                            min_chunk_len = min(c.min_chunk_length for c in children_with_chunks if c.min_chunk_length > 0) if any(c.min_chunk_length > 0 for c in children_with_chunks) else 0
                            max_chunk_len = max(c.max_chunk_length for c in children_with_chunks)
                            # Union of quality issues
                            all_issues = set()
                            for c in children_with_chunks:
                                all_issues.update(c.quality_issues)
                            try:
                                await self._doc_repo.update_quality(
                                    document.parent_id,
                                    quality_score=round(avg_quality, 3),
                                    avg_chunk_length=avg_chunk_len,
                                    min_chunk_length=min_chunk_len,
                                    max_chunk_length=max_chunk_len,
                                    quality_issues=list(all_issues),
                                )
                            except Exception:
                                log.warning("parent.quality_update_failed", exc_info=True)
                        await self._doc_repo.update_status(
                            document.parent_id, parent_status, chunk_count=total_chunks
                        )
                        log.info(
                            "document.parent.aggregated",
                            parent_id=document.parent_id,
                            status=parent_status,
                            total_chunks=total_chunks,
                            children=total,
                        )
                except Exception:
                    log.warning("document.parent.aggregate_failed", exc_info=True)

            # Auto-classify: if no more pending/processing docs in KB
            await self._maybe_trigger_classification(document.kb_id, document.tenant_id, log)

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
            # Auto-classify on failure too (all done = trigger)
            try:
                await self._maybe_trigger_classification(
                    document.kb_id, document.tenant_id, log
                )
            except Exception:
                pass
            # Re-raise so safe_background_task can write to Error Tracking
            raise

    async def _rename_child_page(
        self,
        document_id: str,
        page_number: int,
        content: str,
        kb,
        log,
        tenant_id: str = "",
    ) -> None:
        """Use LLM to generate a semantic filename for a PDF page."""
        if not content or not content.strip():
            return

        # Resolve context_model (reuse the same one for rename)
        model = getattr(kb, "context_model", "") if kb else ""
        if not model and self._tenant_repo:
            try:
                from sqlalchemy import select

                from src.infrastructure.db.engine import async_session_factory
                from src.infrastructure.db.models.tenant_model import TenantModel
                async with async_session_factory() as session:
                    doc = await self._doc_repo.find_by_id(document_id)
                    if doc:
                        stmt = select(TenantModel.default_context_model).where(
                            TenantModel.id == doc.tenant_id
                        )
                        result = await session.execute(stmt)
                        model = result.scalar_one_or_none() or ""
            except Exception:
                pass

        if not model:
            return

        from src.infrastructure.llm.llm_caller import call_llm

        prompt = f"""\
以下是 PDF 第 {page_number} 頁的 OCR 內容（截取前 2000 字）：

{content[:2000]}

請用 5-15 個繁體中文字總結這頁的主題，作為頁面標題。
格式：「第 N 頁 — 主題」，例如「第 3 頁 — 肉品促銷」。
只輸出標題，不要其他內容。"""

        try:
            result = await call_llm(
                model_spec=model,
                prompt=prompt,
                max_tokens=50,
                api_key_resolver=(
                    self._context_service._api_key_resolver
                    if self._context_service and hasattr(self._context_service, '_api_key_resolver')
                    else None
                ),
            )
            new_filename = result.text.strip()[:100]

            # Token-Gov.0: 記錄 PDF 子頁 rename 的 token 用量
            if (
                self._record_usage
                and (result.input_tokens + result.output_tokens) > 0
            ):
                await self._record_usage.execute(
                    tenant_id=tenant_id,
                    request_type=UsageCategory.PDF_RENAME.value,
                    usage=TokenUsage(
                        model=model,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                    ),
                )

            if new_filename:
                # Use independent session to avoid conflicts
                from sqlalchemy import update

                from src.infrastructure.db.engine import async_session_factory
                from src.infrastructure.db.models.document_model import DocumentModel
                async with async_session_factory() as session:
                    await session.execute(
                        update(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .values(filename=new_filename)
                    )
                    await session.commit()
                log.info("child.renamed", document_id=document_id, new_name=new_filename)
        except Exception:
            log.warning("child.rename_llm_failed", exc_info=True)

    async def _maybe_trigger_classification(
        self, kb_id: str, tenant_id: str, log
    ) -> None:
        """If no more pending/processing docs in KB, trigger auto-classification."""
        try:
            # Use independent session to avoid stale data from refreshed sessions
            from sqlalchemy import func, select

            from src.infrastructure.db.engine import async_session_factory
            from src.infrastructure.db.models.document_model import DocumentModel

            async with async_session_factory() as session:
                stmt = (
                    select(func.count())
                    .select_from(DocumentModel)
                    .where(
                        DocumentModel.kb_id == kb_id,
                        DocumentModel.status.in_(["pending", "processing"]),
                        DocumentModel.parent_id.is_(None),
                    )
                )
                result = await session.execute(stmt)
                pending = result.scalar_one()

            log.info("classify_kb.check", kb_id=kb_id, pending=pending)
            if pending == 0:
                from src.infrastructure.queue.arq_pool import enqueue
                await enqueue("classify_kb", kb_id, tenant_id)
                log.info("classify_kb.auto_triggered", kb_id=kb_id)
        except Exception:
            log.warning("classify_kb.auto_trigger_failed", exc_info=True)
