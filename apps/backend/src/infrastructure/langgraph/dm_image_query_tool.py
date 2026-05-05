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
        "回傳結果含 context 文字描述 + sources（含 image_url 的項目由使用者端"
        "自動顯示圖片 — LLM 只需用 context 文字回答，**不要在回覆中嵌入或提及 URL**）。"
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

    async def invoke(  # noqa: C901
        self,
        *,
        tenant_id: str,
        kb_id: str,
        query: str,
        kb_ids: list[str] | None = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> dict[str, Any]:
        # 1. RAG retrieve（支援 multi-KB；空 kb_ids 退回 single kb_id）
        try:
            retrieve_result = await self._rag.retrieve(
                QueryRAGCommand(
                    tenant_id=tenant_id,
                    kb_id=kb_id,
                    kb_ids=kb_ids,
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

        # 4.5 第二層 dedup：同一張實體 PNG（同 storage_path）只保留分數最高的
        # 一筆。原因：catalog PDF 被重新處理 / 重新上傳會生出不同
        # document_id 的子頁，但底下指向同樣的 storage_path。第一層 by_doc
        # dedup 抓不到。在 source 層處理讓 LINE / Web / Widget 所有通路自動
        # 一致，不需要每個 channel handler 各自實作。
        # ordered 已按 score DESC 排序，所以 keep-first = 保留高分。
        seen_paths: set[str] = set()
        deduped: list[Any] = []
        for src in ordered:
            doc = doc_map.get(src.document_id)
            if doc is None or not doc.storage_path:
                continue
            if doc.storage_path in seen_paths:
                continue
            seen_paths.add(doc.storage_path)
            deduped.append(src)

        # 5. 並行生 signed URL（過濾條件：必須是 image/*）
        async def enrich(src: Any) -> dict[str, Any] | None:
            doc = doc_map.get(src.document_id)
            if doc is None or not doc.storage_path:
                return None
            # 防禦：dm tool 只該推圖片；非 image/* 的 doc（FAQ KB 的 JSON 等）
            # 即使被搜到也不該塞進 LINE Flex carousel
            content_type = (doc.content_type or "").lower()
            if not content_type.startswith("image/"):
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

        enriched = await asyncio.gather(*[enrich(s) for s in deduped])
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
