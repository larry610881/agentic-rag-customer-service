"""Outbox Event Factories — 收斂事件建構，避免散落各 use case 重組 payload。

Phase B-D 的 use case 透過這些 factory 產生 OutboxEvent 後，由
PublishOutboxEventUseCase 寫入。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.outbox.entity import OutboxEvent, OutboxEventType


def vector_delete_event(
    *,
    tenant_id: str,
    aggregate_type: str,
    aggregate_id: str,
    collection: str,
    filters: dict[str, Any],
    doc_watermark_ts: datetime | None = None,
) -> OutboxEvent:
    """Filter-based vector delete（DeleteDocument / DeleteChunk / DeleteByBource 用）。

    `filters` 對齊 MilvusVectorStore.delete() 的 filters 參數格式
    （`{"document_id": "..."}`、`{"document_id": ["a","b"]}` IN list、
    `{"tenant_id": "...", "source": "...", "source_id": [...]}` 多條件 AND）。
    """
    return OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=OutboxEventType.VECTOR_DELETE.value,
        payload={"collection": collection, "filters": filters},
        doc_watermark_ts=doc_watermark_ts,
    )


def vector_drop_collection_event(
    *,
    tenant_id: str,
    aggregate_id: str,
    collection: str,
) -> OutboxEvent:
    """整個 collection 刪掉（DeleteKnowledgeBase 用）— 比 N+1 filter delete
    快 N 倍，且天然冪等（drop 已不存在的 collection 是 no-op）。
    """
    return OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type="knowledge_base",
        aggregate_id=aggregate_id,
        event_type=OutboxEventType.VECTOR_DROP_COLLECTION.value,
        payload={"collection": collection},
    )
