"""DmImageQueryTool — RAG 檢索 + 反查子頁 PNG 並回傳 GCS signed URL。

設計：
- 重用 QueryRAGUseCase.retrieve 做 vector search
- 依 document_id 去重（同 doc 取最高 score）
- batch 反查 documents 拿 storage_path
- 並行對 storage_path 生 signed URL
- image_url 放在 sources 欄位（不在 context）
- LLM 看不到 URL；channel handler (LINE / Web) 從 sources 取出渲染
"""

import asyncio
from typing import Any

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.shared.exceptions import NoRelevantKnowledgeError


def _truncate(text: str, max_len: int) -> str:
    text = text.strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


class DmImageQueryTool:
    """查詢 catalog PDF KB（如家樂福 DM）並回傳每個命中子頁的原始 PNG URL。"""

    name = "query_dm_with_image"
    description = (
        "查詢家樂福 DM（型錄）知識庫並回傳對應頁面的 PNG 圖片。"
        "請務必在以下情境使用本工具，勿改用 rag_query："
        "促銷 / 優惠 / 特價 / 折扣 / 買一送一 / 便宜 / 划算；"
        "商品價格 / 目前活動 / DM / 傳單 / 廣告 / 型錄；"
        "特定商品（衛生紙 / 牛奶 / 零食 / 家電 / 生鮮 / 飲料 / 清潔用品 等）。"
        "回傳結果含 context 文字描述 + sources，圖片 URL 由系統自動推送 LINE Flex"
        " carousel；LLM 只需用 context 文字回答，不要在回覆中嵌入或提及 URL。"
    )

    def __init__(
        self,
        query_rag_use_case: QueryRAGUseCase,
        document_repository: DocumentRepository,
        file_storage: DocumentFileStorageService,
        signed_url_ttl_seconds: int = 3600,
        max_images: int = 12,
    ) -> None:
        self._rag = query_rag_use_case
        self._doc_repo = document_repository
        self._storage = file_storage
        self._ttl = signed_url_ttl_seconds
        self._max_images = max_images

    async def invoke(
        self,
        *,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> dict[str, Any]:
        # 1. RAG retrieve
        try:
            retrieve_result = await self._rag.retrieve(
                QueryRAGCommand(
                    tenant_id=tenant_id,
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                ),
            )
        except NoRelevantKnowledgeError:
            return {"success": True, "context": "", "sources": []}

        if not retrieve_result.sources:
            return {"success": True, "context": "", "sources": []}

        # 2. 依 document_id 去重，取每 doc 最高 score 的 source 當 caption
        by_doc: dict[str, Any] = {}
        for src in retrieve_result.sources:
            if not src.document_id:
                continue
            existing = by_doc.get(src.document_id)
            if existing is None or src.score > existing.score:
                by_doc[src.document_id] = src

        if not by_doc:
            return {"success": True, "context": "", "sources": []}

        # 3. 排序 + cap
        ordered = sorted(
            by_doc.values(), key=lambda s: s.score, reverse=True
        )[: self._max_images]

        # 4. Batch 反查 documents
        docs = await self._doc_repo.find_by_ids([s.document_id for s in ordered])
        doc_map = {d.id.value: d for d in docs}

        # 5. 並行生 signed URL（缺 storage_path / get_preview_url 回 None 都過濾）
        async def enrich(src: Any) -> dict[str, Any] | None:
            doc = doc_map.get(src.document_id)
            if doc is None or not doc.storage_path:
                return None
            url = await self._storage.get_preview_url(
                doc.storage_path, expiry_seconds=self._ttl
            )
            if not url:
                return None
            return {
                "document_id": src.document_id,
                "document_name": doc.filename,
                "page_number": doc.page_number or 0,
                "content_snippet": src.content_snippet,
                "score": round(src.score, 3),
                "image_url": url,
            }

        enriched = await asyncio.gather(*[enrich(s) for s in ordered])
        sources = [s for s in enriched if s is not None]

        # 6. context 給 LLM 用（純文字，不含 URL）
        context = "\n---\n".join(
            _truncate(s["content_snippet"], 500) for s in sources
        )

        return {
            "success": True,
            "context": context,
            "sources": sources,
        }
