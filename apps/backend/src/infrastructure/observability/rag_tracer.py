"""RAG Tracer — 記錄 RAG 查詢鏈路的追蹤器

使用方式：
    tracer = RAGTracer()
    trace = tracer.start_trace("退貨政策", "tenant-1")

    # ... embed step ...
    trace.add_step("embed", embed_ms)

    # ... retrieve step ...
    trace.add_step("retrieve", retrieve_ms, chunk_count=5)

    # ... finish ...
    trace.finish(total_ms)
    record = tracer.get_trace(trace.trace_id)
"""

import structlog
from contextvars import ContextVar

from src.domain.observability.trace_record import RAGTraceRecord

logger = structlog.get_logger(__name__)

# Request-scoped trace buffer
_rag_traces: ContextVar[dict[str, RAGTraceRecord] | None] = ContextVar(
    "_rag_traces", default=None
)


class RAGTracer:
    """RAG 查詢追蹤器 — per-request 生命週期"""

    @staticmethod
    def init() -> None:
        """初始化追蹤 buffer（每個 request 開始時呼叫）"""
        _rag_traces.set({})

    @staticmethod
    def start_trace(
        query: str,
        tenant_id: str,
        message_id: str | None = None,
    ) -> RAGTraceRecord:
        """開始一個新的 RAG 追蹤"""
        traces = _rag_traces.get()
        if traces is None:
            traces = {}
            _rag_traces.set(traces)

        record = RAGTraceRecord(
            query=query,
            tenant_id=tenant_id,
            message_id=message_id,
        )
        traces[record.trace_id] = record

        logger.debug(
            "rag_trace.start",
            trace_id=record.trace_id,
            query=query[:100],
            tenant_id=tenant_id,
        )
        return record

    @staticmethod
    def get_trace(trace_id: str) -> RAGTraceRecord | None:
        """取得追蹤記錄"""
        traces = _rag_traces.get()
        if traces is None:
            return None
        return traces.get(trace_id)

    @staticmethod
    def flush() -> list[RAGTraceRecord]:
        """清空並回傳所有追蹤記錄"""
        traces = _rag_traces.get()
        _rag_traces.set(None)
        if not traces:
            return []

        records = list(traces.values())
        for record in records:
            logger.info(
                "rag_trace.complete",
                trace_id=record.trace_id,
                query=record.query[:100],
                total_ms=record.total_ms,
                chunk_count=record.chunk_count,
                steps=len(record.steps),
            )
        return records
