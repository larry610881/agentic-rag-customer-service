"""Extract KB-level DM metadata from cover/promotion page chunks (Issue #47 L3.4).

Use case fired after KB 全 child docs done（L3.6 trigger）。流程：

1. Resolve ``dm_metadata_model``（KB.dm_metadata_model → tenant default → skip）
2. 從 KB 內挑「最可能含 DM-level metadata」的 chunks
   - 啟發式 a：每個 top-level doc 的「第一頁 child」+「最後一頁 child」
     （cover / index / 結尾頁通常含 DM 期間 + 全 DM 活動）
   - 啟發式 b：chunks 開頭含【偵測類型】promotion 或 cover 的（PR-1
     auto-dispatch 注入的 marker）
   - 實作：取 a 提交即可（避免複雜邏輯，cover 類頁本來就少）
3. ``LLMDMMetadataExtractor.extract(...)`` schema-validated dict
4. ``kb_repo.update(kb_id, dm_metadata=...)`` 寫回
5. ``record_usage`` 記錄 token（cache-aware）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.knowledge.services import DMMetadataExtractor
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory
from src.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase

logger = get_logger(__name__)

MAX_EXCERPTS = 30  # 取 top N chunks，控制 token 預算


class ExtractKBDMMetadataUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        extractor: DMMetadataExtractor,
        record_usage: "RecordUsageUseCase | None" = None,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._doc_repo = document_repository
        self._extractor = extractor
        self._record_usage = record_usage

    async def execute(self, kb_id: str, tenant_id: str) -> dict:
        log = logger.bind(kb_id=kb_id, tenant_id=tenant_id)
        log.info("extract_dm_metadata.start")

        kb = await self._kb_repo.find_by_id(kb_id)
        if kb is None:
            log.warning("extract_dm_metadata.kb_not_found")
            return {}

        # 1. Resolve model — KB → tenant default → skip
        model = getattr(kb, "dm_metadata_model", "") or ""
        if not model:
            model = await self._resolve_tenant_default(tenant_id)
        if not model:
            log.info("extract_dm_metadata.no_model_skip")
            return {}

        # 2. 挑可能含 DM-level metadata 的 chunks
        excerpts, page_types = await self._collect_excerpts(kb_id)
        if not excerpts:
            log.info("extract_dm_metadata.no_excerpts")
            return {}

        log.info(
            "extract_dm_metadata.excerpts_collected",
            count=len(excerpts),
            page_types=page_types,
        )

        # 3. LLM 抽取
        result = await self._extractor.extract(
            ocr_excerpts=excerpts,
            page_types=page_types,
            model=model,
        )

        if not result:
            log.warning("extract_dm_metadata.empty_result")
            return {}

        # 4. 寫回 KB.dm_metadata
        await self._kb_repo.update(kb_id, dm_metadata=result)

        # 5. Record usage（cache-aware）
        await self._record_token_usage(kb_id, tenant_id, log)

        log.info(
            "extract_dm_metadata.done",
            dm_period=result.get("dm_period", ""),
            merchant=result.get("merchant", ""),
            global_activity_count=len(result.get("global_activities", [])),
            featured_category_count=len(result.get("featured_categories", [])),
        )
        return result

    async def _resolve_tenant_default(self, tenant_id: str) -> str:
        """KB 沒設 dm_metadata_model 時 fallback tenant default（若有）。"""
        # 暫無 tenant.default_dm_metadata_model 欄位 — 若未來加，於此 query。
        # 目前直接返回空字串（caller 視為「未啟用」skip）。
        return ""

    async def _collect_excerpts(
        self, kb_id: str
    ) -> tuple[list[str], list[str]]:
        """挑 KB 內 ≤ MAX_EXCERPTS 個含 DM-level metadata 的 chunks。

        策略：
        - 撈所有 chunks 的 (content, page_number) — JOIN documents
        - 優先挑含【偵測類型】(promotion|cover|mixed) marker 的 chunks
          （PR-1 auto-dispatch 注入）
        - 補：每個 parent doc 的「page_number=1」child + 「最大 page_number」child
          的 chunks（cover / 結尾頁啟發式）
        - 上限 MAX_EXCERPTS 控 token
        """
        from sqlalchemy import select

        from src.infrastructure.db.engine import async_session_factory
        from src.infrastructure.db.models.chunk_model import ChunkModel
        from src.infrastructure.db.models.document_model import DocumentModel

        excerpts: list[str] = []
        page_types: list[str] = []

        async with async_session_factory() as session:
            # 取所有 child docs 的 page_number 和對應 chunks
            stmt = (
                select(
                    DocumentModel.id,
                    DocumentModel.page_number,
                    ChunkModel.content,
                )
                .join(ChunkModel, ChunkModel.document_id == DocumentModel.id)
                .where(
                    DocumentModel.kb_id == kb_id,
                    DocumentModel.parent_id.is_not(None),
                )
                .order_by(
                    DocumentModel.page_number, ChunkModel.chunk_index
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

        if not rows:
            return [], []

        # Group by page_number → first chunk of each page used as excerpt source
        # （取每頁第一個 chunk content，已含【偵測類型】+【商家】等 markers）
        chunks_by_page: dict[int, str] = {}
        for _doc_id, page_no, content in rows:
            if page_no is None:
                continue
            if page_no not in chunks_by_page:
                chunks_by_page[page_no] = content[:2000]  # cap each excerpt

        if not chunks_by_page:
            return [], []

        # 優先級：
        # 1. 含【偵測類型】(promotion|cover|mixed) 的頁
        # 2. 第一頁 + 最後一頁
        # 3. 補到 MAX_EXCERPTS 用其他頁（隨機 / 中間頁）
        sorted_pages = sorted(chunks_by_page.keys())
        first_page = sorted_pages[0] if sorted_pages else None
        last_page = sorted_pages[-1] if sorted_pages else None

        priority_1: list[tuple[int, str, str]] = []  # (page_no, type, content)
        priority_2: list[tuple[int, str, str]] = []
        priority_3: list[tuple[int, str, str]] = []

        for page_no, content in chunks_by_page.items():
            ptype = self._infer_page_type(content)
            if ptype in ("promotion", "cover", "mixed"):
                priority_1.append((page_no, ptype, content))
            elif page_no == first_page or page_no == last_page:
                priority_2.append((page_no, ptype or "boundary", content))
            else:
                priority_3.append((page_no, ptype or "catalog", content))

        # 取 priority_1 全部 + priority_2 + priority_3 補到上限
        selected = priority_1 + priority_2 + priority_3
        selected.sort(key=lambda r: r[0])  # 按 page_number 排序
        selected = selected[:MAX_EXCERPTS]

        for page_no, ptype, content in selected:
            excerpts.append(f"[Page {page_no}]\n{content}")
            page_types.append(ptype)

        return excerpts, page_types

    @staticmethod
    def _infer_page_type(content: str) -> str:
        """從 chunk content 開頭【偵測類型】marker 推測 page type。"""
        if "【偵測類型】promotion" in content:
            return "promotion"
        if "【偵測類型】cover" in content:
            return "cover"
        if "【偵測類型】mixed" in content:
            return "mixed"
        if "【偵測類型】catalog" in content:
            return "catalog"
        # Fallback：若無 marker（舊資料、catalog mode），看內容特徵
        if "【活動主題】" in content or "【活動期間】" in content:
            return "promotion"
        if "【DM 名稱】" in content or "【DM 期間】" in content:
            return "cover"
        return "catalog"

    async def _record_token_usage(
        self, kb_id: str, tenant_id: str, log
    ) -> None:
        """Record token usage with cache-aware fields. Mirror classify_kb."""
        if not self._record_usage:
            return
        total = (
            self._extractor.last_input_tokens
            + self._extractor.last_output_tokens
        )
        if total <= 0:
            return
        try:
            # Session refresh — LLM 長 call 後 session 可能超時
            from src.infrastructure.db.engine import async_session_factory
            _new_session = async_session_factory()
            if (
                hasattr(self._record_usage, "_repo")
                and hasattr(self._record_usage._repo, "_session")
            ):
                self._record_usage._repo._session = _new_session
        except Exception:
            pass

        await self._record_usage.execute(
            tenant_id=tenant_id,
            request_type=UsageCategory.AUTO_CLASSIFICATION.value,  # 暫用既有 category
            usage=TokenUsage(
                model=self._extractor.last_model,
                input_tokens=self._extractor.last_input_tokens,
                output_tokens=self._extractor.last_output_tokens,
                cache_read_tokens=self._extractor.last_cache_read_tokens,
                cache_creation_tokens=self._extractor.last_cache_creation_tokens,
            ),
            kb_id=kb_id,
        )
