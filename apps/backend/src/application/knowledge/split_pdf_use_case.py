"""Split PDF into per-page PNG documents for parallel OCR processing."""

import gc

from src.domain.knowledge.entity import Document, ProcessingTask
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.knowledge.value_objects import DocumentId, ProcessingTaskId
from src.infrastructure.file_parser.pdf_page_extractor import count_pages, iter_pages_as_images
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class SplitPdfUseCase:
    """Split a PDF into per-page PNG child documents and enqueue parallel OCR jobs."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        knowledge_base_repository: KnowledgeBaseRepository,
        processing_task_repository: ProcessingTaskRepository,
        document_file_storage: DocumentFileStorageService,
    ) -> None:
        self._doc_repo = document_repository
        self._kb_repo = knowledge_base_repository
        self._task_repo = processing_task_repository
        self._file_storage = document_file_storage

    async def execute(self, parent_doc_id: str, task_id: str) -> None:
        """Split PDF into pages, create child documents, enqueue OCR jobs."""
        from src.infrastructure.queue.arq_pool import enqueue

        # Update task status
        await self._task_repo.update_status(task_id, "processing", progress=0)

        parent = await self._doc_repo.find_by_id(parent_doc_id)
        if parent is None:
            await self._task_repo.update_status(task_id, "failed", error_message="Document not found")
            return

        await self._doc_repo.update_status(parent_doc_id, "processing")

        # Load PDF from storage
        try:
            raw_content = await self._file_storage.load(parent.storage_path)
        except Exception as e:
            logger.error("split_pdf.load_failed", doc_id=parent_doc_id, error=str(e))
            await self._doc_repo.update_status(parent_doc_id, "failed")
            await self._task_repo.update_status(task_id, "failed", error_message=str(e))
            return

        # Count pages first (lightweight, no rendering)
        total_pages = count_pages(raw_content)
        logger.info("split_pdf.pages_counted", doc_id=parent_doc_id, pages=total_pages)

        if total_pages == 0:
            await self._doc_repo.update_status(parent_doc_id, "failed")
            await self._task_repo.update_status(task_id, "failed", error_message="PDF has no pages")
            return

        # Process one page at a time to minimize memory usage
        page_num = 0
        for png_bytes in iter_pages_as_images(raw_content):
            page_num += 1
            child_id = DocumentId()
            child_filename = f"page_{page_num:03d}.png"

            # Save PNG to GCS
            storage_path = await self._file_storage.save(
                parent.tenant_id,
                child_id.value,
                png_bytes,
                child_filename,
            )

            # Free PNG bytes immediately
            del png_bytes

            # Create child document
            child = Document(
                id=child_id,
                kb_id=parent.kb_id,
                tenant_id=parent.tenant_id,
                filename=child_filename,
                content_type="image/png",
                content="",
                raw_content=b"",
                storage_path=storage_path,
                status="pending",
                parent_id=parent_doc_id,
                page_number=page_num,
            )
            await self._doc_repo.save(child)

            # Create processing task for child
            child_task = ProcessingTask(
                id=ProcessingTaskId(),
                document_id=child_id.value,
                tenant_id=parent.tenant_id,
            )
            await self._task_repo.save(child_task)

            # Enqueue OCR job
            await enqueue("process_document", child_id.value, child_task.id.value)

            # Update parent task progress
            progress = round((page_num / total_pages) * 30)
            await self._task_repo.update_status(task_id, "processing", progress=progress)

            # Force GC every 10 pages to reclaim memory
            if page_num % 10 == 0:
                gc.collect()

        # Free PDF bytes
        del raw_content
        gc.collect()

        logger.info(
            "split_pdf.done",
            doc_id=parent_doc_id,
            pages=total_pages,
            children_enqueued=page_num,
        )

        # Mark parent task as completed (children have their own tasks)
        await self._task_repo.update_status(task_id, "completed", progress=100)
