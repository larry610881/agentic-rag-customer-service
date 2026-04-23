"""Agent Trace Filter Builder + Conversation Grouping — S-Gov.6a

設計重點：
- `build_where(filters)` 純 function 回傳 SQLAlchemy where 條件 list，
  flat 與 grouped query 共用同一組 filter
- `list_traces_grouped_by_conversation` 三步驟：
  1. distinct conversation_id (按最近 trace 時間 desc 分頁)
  2. 一次撈這 N 個 conv 的所有 trace
  3. Python 層 group by 維持排序

不走 DDD 完整 Repository pattern — observability 一直是直接 query layer。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, Text, distinct, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.agent_trace_model import (
    AgentExecutionTraceModel,
)
from src.infrastructure.db.models.conversation_model import ConversationModel
from src.infrastructure.db.models.message_model import MessageModel


@dataclass(frozen=True)
class TraceFilters:
    """所有 filter 維度集中於此 dataclass，方便傳遞與測試。"""

    tenant_id: str | None = None
    agent_mode: str | None = None
    conversation_id: str | None = None
    date_from: str | None = None  # ISO8601
    date_to: str | None = None
    source: str | None = None  # web | widget | line
    bot_id: str | None = None
    outcome: str | None = None  # success | failed | partial
    min_total_ms: float | None = None
    max_total_ms: float | None = None
    min_total_tokens: int | None = None
    max_total_tokens: int | None = None
    keyword: str | None = None  # ILIKE on nodes::text


def _parse_iso(value: str) -> datetime:
    """ISO8601 string → tz-aware datetime（'Z' 結尾視為 UTC）。"""
    s = value.replace("Z", "+00:00") if value.endswith("Z") else value
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_where(filters: TraceFilters) -> list[Any]:
    """從 TraceFilters 組 SQLAlchemy where 條件 list。"""
    T = AgentExecutionTraceModel  # noqa: N806
    conditions: list[Any] = []

    if filters.tenant_id is not None:
        conditions.append(T.tenant_id == filters.tenant_id)
    if filters.agent_mode:
        conditions.append(T.agent_mode == filters.agent_mode)
    if filters.conversation_id:
        conditions.append(T.conversation_id == filters.conversation_id)
    # PostgreSQL 不接受 `timestamptz >= str` 直接比較
    # → parse ISO8601 (含 'Z' 結尾的 UTC) 為 datetime
    if filters.date_from:
        conditions.append(T.created_at >= _parse_iso(filters.date_from))
    if filters.date_to:
        conditions.append(T.created_at <= _parse_iso(filters.date_to))
    if filters.source:
        conditions.append(T.source == filters.source)
    if filters.bot_id:
        conditions.append(T.bot_id == filters.bot_id)
    if filters.outcome:
        conditions.append(T.outcome == filters.outcome)
    if filters.min_total_ms is not None:
        conditions.append(T.total_ms >= filters.min_total_ms)
    if filters.max_total_ms is not None:
        conditions.append(T.total_ms <= filters.max_total_ms)
    if filters.min_total_tokens is not None:
        # total_tokens 是 JSON dict {input, output, total} — 用 ->> 取 total 並 cast int
        conditions.append(
            T.total_tokens["total"].as_string().cast(Integer)
            >= filters.min_total_tokens
        )
    if filters.max_total_tokens is not None:
        conditions.append(
            T.total_tokens["total"].as_string().cast(Integer)
            <= filters.max_total_tokens
        )
    if filters.keyword:
        # PostgreSQL JSON cast to text 會 escape 中文（\u9000\u8ca8）
        # 改 cast(JSONB)::text 才會 decode 成原文
        # POC < 10K traces 可接受；未來升級 pg_trgm GIN index
        conditions.append(
            T.nodes.cast(JSONB).cast(Text).ilike(f"%{filters.keyword}%")
        )

    return conditions


@dataclass(frozen=True)
class ConversationTraceGroup:
    conversation_id: str
    trace_count: int
    first_at: datetime
    last_at: datetime
    traces: list[dict[str, Any]]
    # S-KB-Followup.1 Lv1: UUID prefix 認不出對話 → 補 message preview + summary
    first_user_message: str | None = None  # 使用者第一句（截 200 字）
    last_assistant_answer: str | None = None  # Bot 最後回覆（截 200 字）
    summary: str | None = None  # conversations.summary（若 LLM 已生）


def trace_to_dict(r: AgentExecutionTraceModel) -> dict[str, Any]:
    """ORM model → API response dict（與 endpoint 既有格式一致 + outcome 欄位）"""
    return {
        "id": r.id,
        "trace_id": r.trace_id,
        "tenant_id": r.tenant_id,
        "message_id": r.message_id,
        "conversation_id": r.conversation_id,
        "agent_mode": r.agent_mode,
        "source": getattr(r, "source", ""),
        "llm_model": getattr(r, "llm_model", ""),
        "llm_provider": getattr(r, "llm_provider", ""),
        "bot_id": getattr(r, "bot_id", None),
        "nodes": r.nodes,
        "total_ms": r.total_ms,
        "total_tokens": r.total_tokens,
        "outcome": getattr(r, "outcome", None),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def list_traces_grouped_by_conversation(
    session: AsyncSession,
    *,
    filters: TraceFilters,
    limit: int,
    offset: int,
) -> tuple[list[ConversationTraceGroup], int]:
    """按 conversation_id 聚合 trace。

    Pagination 以「conversation 數」為單位，不是「trace 數」。
    """
    T = AgentExecutionTraceModel  # noqa: N806
    where = build_where(filters)
    # conversation_id IS NULL 的 trace 不納入 grouped 視圖（無從 group）
    where_with_conv = [*where, T.conversation_id.isnot(None)]

    # Step 1: distinct conversation_id（按該 conv 最近 trace 時間 desc 分頁）
    conv_ids_stmt = (
        select(
            T.conversation_id.label("cid"),
            func.max(T.created_at).label("latest"),
        )
        .where(*where_with_conv)
        .group_by(T.conversation_id)
        .order_by(func.max(T.created_at).desc())
        .limit(limit)
        .offset(offset)
    )
    conv_id_rows = (await session.execute(conv_ids_stmt)).all()
    conv_ids = [row.cid for row in conv_id_rows]

    # 總 conversation 數（給前端分頁）
    total_stmt = select(
        func.count(distinct(T.conversation_id))
    ).where(*where_with_conv)
    total = (await session.execute(total_stmt)).scalar() or 0

    if not conv_ids:
        return [], int(total)

    # Step 2: 一次撈這 N 個 conv 的所有 trace（按時間升序，便於聚合排序）
    traces_stmt = (
        select(T)
        .where(T.conversation_id.in_(conv_ids), *where)
        .order_by(T.created_at.asc())
    )
    trace_rows = (await session.execute(traces_stmt)).scalars().all()

    # Step 3: Python 層 group by + maintain conv_ids 排序
    by_conv: dict[str, list[AgentExecutionTraceModel]] = defaultdict(list)
    for trace in trace_rows:
        by_conv[trace.conversation_id].append(trace)

    # Step 4 (Lv1): 為這 N 個 conversation 一次撈 preview
    # - first_user_message: 最早的 role='user' 訊息（截 200 字）
    # - last_assistant_answer: 最晚的 role='assistant' 訊息（截 200 字）
    # - summary: conversations.summary（若 conv summary job 已跑）
    preview_by_conv = await _load_conversation_previews(session, conv_ids)

    groups: list[ConversationTraceGroup] = []
    for cid in conv_ids:
        traces = by_conv.get(cid, [])
        if not traces:
            continue
        prev = preview_by_conv.get(cid, {})
        groups.append(
            ConversationTraceGroup(
                conversation_id=cid,
                trace_count=len(traces),
                first_user_message=prev.get("first_user_message"),
                last_assistant_answer=prev.get("last_assistant_answer"),
                summary=prev.get("summary"),
                first_at=traces[0].created_at,
                last_at=traces[-1].created_at,
                traces=[trace_to_dict(t) for t in traces],
            )
        )

    return groups, int(total)


_PREVIEW_LEN = 200


def _truncate(text: str | None) -> str | None:
    if text is None:
        return None
    return text[:_PREVIEW_LEN]


async def _load_conversation_previews(
    session: AsyncSession,
    conv_ids: list[str],
) -> dict[str, dict[str, str | None]]:
    """為指定 conversation_ids 撈 preview 欄位（one-shot query）。

    Returns:
        {cid: {"first_user_message": str|None,
               "last_assistant_answer": str|None,
               "summary": str|None}}
    """
    if not conv_ids:
        return {}

    result: dict[str, dict[str, str | None]] = {
        cid: {
            "first_user_message": None,
            "last_assistant_answer": None,
            "summary": None,
        }
        for cid in conv_ids
    }

    # 1. conversations.summary — 1 query
    summary_rows = (
        await session.execute(
            select(ConversationModel.id, ConversationModel.summary).where(
                ConversationModel.id.in_(conv_ids)
            )
        )
    ).all()
    for row in summary_rows:
        result[row.id]["summary"] = _truncate(row.summary)

    # 2. first user message per conversation — DISTINCT ON (efficient in PG)
    first_user = (
        await session.execute(
            select(
                MessageModel.conversation_id,
                MessageModel.content,
            )
            .where(
                MessageModel.conversation_id.in_(conv_ids),
                MessageModel.role == "user",
            )
            .order_by(
                MessageModel.conversation_id,
                MessageModel.created_at.asc(),
            )
            .distinct(MessageModel.conversation_id)
        )
    ).all()
    for row in first_user:
        result[row.conversation_id]["first_user_message"] = _truncate(row.content)

    # 3. last assistant answer per conversation
    last_asst = (
        await session.execute(
            select(
                MessageModel.conversation_id,
                MessageModel.content,
            )
            .where(
                MessageModel.conversation_id.in_(conv_ids),
                MessageModel.role == "assistant",
            )
            .order_by(
                MessageModel.conversation_id,
                MessageModel.created_at.desc(),
            )
            .distinct(MessageModel.conversation_id)
        )
    ).all()
    for row in last_asst:
        result[row.conversation_id]["last_assistant_answer"] = _truncate(row.content)

    return result
