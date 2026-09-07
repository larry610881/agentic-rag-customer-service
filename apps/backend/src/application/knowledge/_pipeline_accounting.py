"""文件管線（process / reprocess）共用的用量記帳 helper（Issue #73）

過去只有 ``ProcessDocumentUseCase`` 記 OCR / contextual retrieval / embedding，
``ReprocessDocumentUseCase`` 整條管線沒入帳。兩個 use case 現在都呼叫這裡的
函式，記帳規則只有一份，避免再 drift。

OCR 與 contextual retrieval 的用量仍來自服務物件的 ``last_*`` 累計屬性
（既有 stateful 約定，見 architecture-journal「累計屬性 Pattern」）；
embedding 改走 ``EmbeddingResult``（供應商回傳）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.application.usage.embedding_accounting import account_embedding
from src.domain.rag.services import EmbeddingResult
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase

logger = structlog.get_logger(__name__)

_DEFAULT_OCR_MODEL = "claude-haiku-4-5-20251001"


def _int_attr(source: Any, name: str) -> int:
    """讀服務物件的整數累計屬性；缺少或非 int（例如 mock）一律視為 0。"""
    value = getattr(source, name, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def reset_llm_counters(source: Any) -> None:
    """OCR 引擎為 singleton，直接呼叫引擎前先歸零累計屬性。"""
    for name in (
        "last_input_tokens",
        "last_output_tokens",
        "last_cache_read_tokens",
        "last_cache_creation_tokens",
    ):
        if isinstance(getattr(source, name, None), int):
            setattr(source, name, 0)


async def _record(
    record_usage: "RecordUsageUseCase | None",
    *,
    category: UsageCategory,
    tenant_id: str,
    kb_id: str,
    usage: TokenUsage,
) -> None:
    if record_usage is None or usage.total_tokens <= 0:
        return
    try:
        await record_usage.execute(
            tenant_id=tenant_id,
            request_type=category.value,
            usage=usage,
            kb_id=kb_id,
        )
    except Exception:
        logger.warning(
            "document_pipeline.usage_record_failed",
            request_type=category.value,
            tenant_id=tenant_id,
            kb_id=kb_id,
            exc_info=True,
        )


async def record_ocr_usage(
    record_usage: "RecordUsageUseCase | None",
    *,
    source: Any,
    tenant_id: str,
    kb_id: str,
) -> None:
    """``source`` 為 file parser 或 OCR 引擎（兩者都有 last_* 累計屬性）。"""
    in_tok = _int_attr(source, "last_input_tokens")
    out_tok = _int_attr(source, "last_output_tokens")
    if in_tok + out_tok <= 0:
        return
    model = getattr(source, "last_model", "") or getattr(source, "_model", "")
    if not isinstance(model, str) or not model:
        model = _DEFAULT_OCR_MODEL
    await _record(
        record_usage,
        category=UsageCategory.OCR,
        tenant_id=tenant_id,
        kb_id=kb_id,
        usage=TokenUsage(model=model, input_tokens=in_tok, output_tokens=out_tok),
    )


async def record_context_usage(
    record_usage: "RecordUsageUseCase | None",
    *,
    context_service: Any,
    tenant_id: str,
    kb_id: str,
    fallback_model: str,
) -> None:
    """Contextual retrieval（S-LLM-Cache.1：含 cache_read / cache_creation）。"""
    in_tok = _int_attr(context_service, "last_input_tokens")
    out_tok = _int_attr(context_service, "last_output_tokens")
    if in_tok + out_tok <= 0:
        return
    model = getattr(context_service, "last_model", "")
    await _record(
        record_usage,
        category=UsageCategory.CONTEXTUAL_RETRIEVAL,
        tenant_id=tenant_id,
        kb_id=kb_id,
        usage=TokenUsage(
            model=model if isinstance(model, str) and model else fallback_model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cache_read_tokens=_int_attr(context_service, "last_cache_read_tokens"),
            cache_creation_tokens=_int_attr(
                context_service, "last_cache_creation_tokens"
            ),
        ),
    )


async def record_embedding_usage(
    record_usage: "RecordUsageUseCase | None",
    *,
    result: EmbeddingResult,
    tenant_id: str,
    kb_id: str,
) -> None:
    await account_embedding(
        record_usage,
        tenant_id=tenant_id,
        result=result,
        category=UsageCategory.EMBEDDING,
        kb_id=kb_id,
    )
