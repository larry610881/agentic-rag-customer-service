from src.domain.knowledge.entity import Document
from src.domain.knowledge.repository import DocumentRepository


class ListDocumentsUseCase:
    def __init__(self, document_repository: DocumentRepository) -> None:
        self._doc_repo = document_repository

    async def execute(
        self,
        kb_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Document]:
        # UI 列表只顯示 top-level documents（parent_id IS NULL），
        # 子頁靠 children_count + 展開查看，不佔分頁。
        return await self._doc_repo.find_top_level_by_kb(
            kb_id, limit=limit, offset=offset,
        )

    async def count(self, kb_id: str) -> int:
        # 與 execute() 一致，只算 top-level，確保 total_pages 正確。
        return await self._doc_repo.count_top_level_by_kb(kb_id)
