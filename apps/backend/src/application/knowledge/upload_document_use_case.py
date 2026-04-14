from dataclasses import dataclass

from src.domain.knowledge.entity import Document, ProcessingTask
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.knowledge.value_objects import DocumentId, ProcessingTaskId
from src.domain.shared.exceptions import EntityNotFoundError, UnsupportedFileTypeError

# Supported content types for file type validation (no parser needed at upload)
_SUPPORTED_TYPES: set[str] = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "text/xml",
    "application/xml",
    "text/html",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/rtf",
    "text/rtf",
}


@dataclass(frozen=True)
class UploadDocumentCommand:
    kb_id: str
    tenant_id: str
    filename: str
    content_type: str
    raw_content: bytes


@dataclass(frozen=True)
class RequestUploadCommand:
    kb_id: str
    tenant_id: str
    filename: str
    content_type: str


@dataclass
class RequestUploadResult:
    document_id: str
    task_id: str
    upload_url: str
    storage_path: str


@dataclass
class UploadDocumentResult:
    document: Document
    task: ProcessingTask


class UploadDocumentUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        processing_task_repository: ProcessingTaskRepository,
        document_file_storage: DocumentFileStorageService,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._doc_repo = document_repository
        self._task_repo = processing_task_repository
        self._file_storage = document_file_storage

    async def execute(self, command: UploadDocumentCommand) -> UploadDocumentResult:
        # Validate file type
        if command.content_type not in _SUPPORTED_TYPES:
            raise UnsupportedFileTypeError(command.content_type)

        # Verify knowledge base exists
        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", command.kb_id)

        # Create document — store raw bytes, defer parsing to ProcessDocumentUseCase
        document = Document(
            id=DocumentId(),
            kb_id=command.kb_id,
            tenant_id=command.tenant_id,
            filename=command.filename,
            content_type=command.content_type,
            content="",
            raw_content=command.raw_content,
            status="pending",
        )
        await self._doc_repo.save(document)

        # Save file to storage
        storage_path = await self._file_storage.save(
            command.tenant_id,
            document.id.value,
            command.raw_content,
            command.filename,
        )
        await self._doc_repo.update_storage_path(document.id.value, storage_path)
        document.storage_path = storage_path

        # Create processing task
        task = ProcessingTask(
            id=ProcessingTaskId(),
            document_id=document.id.value,
            tenant_id=command.tenant_id,
        )
        await self._task_repo.save(task)

        return UploadDocumentResult(document=document, task=task)

    async def request_upload(self, command: RequestUploadCommand) -> RequestUploadResult:
        """Create document + processing task, return signed URL for direct GCS upload."""
        if command.content_type not in _SUPPORTED_TYPES:
            raise UnsupportedFileTypeError(command.content_type)

        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", command.kb_id)

        doc_id = DocumentId()
        document = Document(
            id=doc_id,
            kb_id=command.kb_id,
            tenant_id=command.tenant_id,
            filename=command.filename,
            content_type=command.content_type,
            content="",
            raw_content=b"",
            status="pending",
        )
        await self._doc_repo.save(document)

        storage_path = f"{command.tenant_id}/{doc_id.value}/{command.filename}"
        await self._doc_repo.update_storage_path(doc_id.value, storage_path)

        task = ProcessingTask(
            id=ProcessingTaskId(),
            document_id=doc_id.value,
            tenant_id=command.tenant_id,
        )
        await self._task_repo.save(task)

        upload_url = await self._file_storage.generate_upload_signed_url(
            tenant_id=command.tenant_id,
            document_id=doc_id.value,
            filename=command.filename,
            content_type=command.content_type,
        )

        return RequestUploadResult(
            document_id=doc_id.value,
            task_id=task.id.value,
            upload_url=upload_url,
            storage_path=storage_path,
        )

    async def confirm_upload(self, document_id: str, task_id: str) -> UploadDocumentResult:
        """Confirm direct upload completed, return document + task for background processing."""
        doc = await self._doc_repo.find_by_id(document_id)
        if doc is None:
            raise EntityNotFoundError("Document", document_id)

        task = await self._task_repo.find_by_id(task_id)
        if task is None:
            raise EntityNotFoundError("ProcessingTask", task_id)

        return UploadDocumentResult(document=doc, task=task)
