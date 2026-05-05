"""Outbox Handlers — event_type → callable 對應

DrainOutboxUseCase dispatch 用此 registry。新事件類型在這註冊就好，
不需動 use case。

handler 必須：
1. Idempotent — drain 重試時不會 double-effect（Milvus filter delete 天然冪等）
2. raise on failure — drain 統一 catch + mark_failed + backoff
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

from src.domain.outbox.entity import OutboxEvent, OutboxEventType
from src.domain.rag.services import VectorStore

logger = structlog.get_logger(__name__)

OutboxHandlerCallable = Callable[[OutboxEvent], Awaitable[None]]


def build_vector_handlers(
    vector_store: VectorStore,
) -> dict[str, "OutboxHandlerCallable"]:
    """工廠 — 由 container 在 wire 時呼叫，避免循環依賴。"""

    async def handle_vector_delete(event: OutboxEvent) -> None:
        collection = event.payload.get("collection", "")
        filters = event.payload.get("filters", {})
        if not collection or not filters:
            raise ValueError(
                f"vector.delete event missing collection/filters: {event.id}"
            )
        # raise_on_error=True 讓 Milvus 真實失敗能進 outbox retry，
        # 而非沿用既有 swallow exception 行為（那是給 in-band caller 的）
        await vector_store.delete(
            collection=collection,
            filters=filters,
            raise_on_error=True,
        )

    async def handle_vector_drop_collection(event: OutboxEvent) -> None:
        collection = event.payload.get("collection", "")
        if not collection:
            raise ValueError(
                f"vector.drop_collection event missing collection: {event.id}"
            )
        # drop 已不存在的 collection 是 no-op（Milvus 行為），天然冪等
        await vector_store.drop_collection(collection)

    return {
        OutboxEventType.VECTOR_DELETE.value: handle_vector_delete,
        OutboxEventType.VECTOR_DROP_COLLECTION.value: handle_vector_drop_collection,
    }
