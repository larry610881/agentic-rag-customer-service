from dataclasses import dataclass

from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class ViewDocumentResult:
    content: bytes
    filename: str
    content_type: str


class ViewDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        document_file_storage: DocumentFileStorageService,
    ) -> None:
        self._doc_repo = document_repository
        self._file_storage = document_file_storage

    async def execute(self, doc_id: str) -> ViewDocumentResult:
        doc = await self._doc_repo.find_by_id(doc_id)
        if doc is None:
            raise EntityNotFoundError("Document", doc_id)

        # Prefer file storage, fallback to DB BYTEA
        content: bytes | None = None
        if doc.storage_path:
            try:
                content = await self._file_storage.load(doc.storage_path)
            except FileNotFoundError:
                pass
        if content is None and doc.raw_content:
            content = doc.raw_content
        if content is None:
            raise ValueError("No file content available for viewing")

        return ViewDocumentResult(
            content=content,
            filename=doc.filename,
            content_type=doc.content_type,
        )
