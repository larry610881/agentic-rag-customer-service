"""Embedding 用量記帳共用 helper（Issue #73）

所有會呼叫 embedding 服務且需要入帳的路徑（文件 ingest / reprocess / reembed /
每輪檢索的查詢 embedding / 對話摘要 / 管理端語意搜尋）一律經此函式寫入
token_usage_records，規則只有一份：

- 用量來自 ``EmbeddingResult``（供應商回傳），不是估算、不是服務物件屬性
- 快取命中（``cache_hit``）沒花 token → 不入帳
- fail-open：記帳失敗只 warn，不能影響主流程（檢索 / 文件處理照常完成）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.domain.rag.services import EmbeddingResult
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase

logger = structlog.get_logger(__name__)


async def account_embedding(
    record_usage: "RecordUsageUseCase | None",
    *,
    tenant_id: str,
    result: EmbeddingResult,
    category: UsageCategory | str,
    bot_id: str | None = None,
    kb_id: str | None = None,
) -> bool:
    """把一次 embedding 呼叫的用量寫入帳本；回傳是否真的寫了一筆。"""
    if record_usage is None or not tenant_id:
        return False
    if result.cache_hit or result.total_tokens <= 0:
        return False
    request_type = (
        category.value if isinstance(category, UsageCategory) else category
    )
    try:
        await record_usage.execute(
            tenant_id=tenant_id,
            request_type=request_type,
            usage=TokenUsage(
                model=result.model,
                input_tokens=result.total_tokens,
                output_tokens=0,
            ),
            bot_id=bot_id,
            kb_id=kb_id,
        )
    except Exception:
        logger.warning(
            "embedding.usage_record_failed",
            request_type=request_type,
            tenant_id=tenant_id,
            exc_info=True,
        )
        return False
    return True
