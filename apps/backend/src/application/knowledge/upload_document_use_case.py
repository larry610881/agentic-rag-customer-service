import asyncio
from dataclasses import dataclass

from src.domain.knowledge.entity import Document, ProcessingTask
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
    ProcessingTaskRepository,
)
from src.domain.knowledge.services import FileParserService
from src.domain.knowledge.value_objects import DocumentId, ProcessingTaskId
from src.domain.shared.exceptions import EntityNotFoundError, UnsupportedFileTypeError


@dataclass(frozen=True)
class UploadDocumentCommand:
    kb_id: str
    tenant_id: str
    filename: str
    content_type: str
    raw_content: bytes


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
        file_parser_service: FileParserService,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._doc_repo = document_repository
        self._task_repo = processing_task_repository
        self._file_parser = file_parser_service

    async def execute(self, command: UploadDocumentCommand) -> UploadDocumentResult:
        # Validate file type
        if command.content_type not in self._file_parser.supported_types():
            raise UnsupportedFileTypeError(command.content_type)

        # Verify knowledge base exists
        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", command.kb_id)

        # Parse file content (offload sync IO to thread to avoid blocking event loop)
        content = await asyncio.to_thread(
            self._file_parser.parse, command.raw_content, command.content_type
        )

        # Create document
        document = Document(
            id=DocumentId(),
            kb_id=command.kb_id,
            tenant_id=command.tenant_id,
            filename=command.filename,
            content_type=command.content_type,
            content=content,
            status="pending",
        )
        await self._doc_repo.save(document)

        # Create processing task
        task = ProcessingTask(
            id=ProcessingTaskId(),
            document_id=document.id.value,
            tenant_id=command.tenant_id,
        )
        await self._task_repo.save(task)

        return UploadDocumentResult(document=document, task=task)
