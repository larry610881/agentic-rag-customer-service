"""LLM-based Reranker — 用 LLM 對 RAG 召回結果重新排序

一次 API call 批量排序，不逐筆送。
支援任何 LangChain ChatModel（Haiku / GPT-4o-mini 等）。
"""

import json
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase

logger = structlog.get_logger(__name__)

_RERANK_SYSTEM_PROMPT = """\
你是搜尋結果排序專家。根據使用者的查詢，為每個搜尋結果評分。

評分標準（0-10）：
- 10: 完全回答了使用者的問題
- 7-9: 包含高度相關的資訊
- 4-6: 部分相關
- 1-3: 幾乎不相關
- 0: 完全不相關

只回覆 JSON array，格式：[{"index": 0, "score": 8}, ...]
不要加任何其他文字。"""


async def llm_rerank(
    query: str,
    chunks: list[dict],
    model: str = "claude-haiku-4-5-20251001",
    top_k: int = 5,
    api_key: str = "",
    record_usage: "RecordUsageUseCase | None" = None,
    tenant_id: str = "",
    bot_id: str | None = None,
) -> list[dict]:
    """Rerank chunks using LLM scoring.

    Args:
        query: User's search query
        chunks: List of chunk dicts (must have 'content' key)
        model: LLM model to use for reranking
        top_k: Number of top results to return
        api_key: Anthropic API key (resolved from DB or env)
        record_usage: Token-Gov.0 — 注入 RecordUsageUseCase 後會記錄
                      rerank LLM 的 token 用量到 token_usage_records
        tenant_id: 對應 record_usage 的 tenant
        bot_id: 對應 record_usage 的 bot

    Returns:
        Reranked list of chunks (top_k items)
    """
    if not chunks or len(chunks) <= top_k:
        return chunks

    # Build the prompt with numbered chunks
    chunk_texts = []
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", chunk.get("content_snippet", ""))
        # Truncate long chunks to save tokens
        if len(content) > 500:
            content = content[:500] + "..."
        chunk_texts.append(f"[{i}] {content}")

    user_prompt = (
        f"查詢：{query}\n\n"
        f"搜尋結果（共 {len(chunks)} 筆）：\n\n"
        + "\n\n".join(chunk_texts)
    )

    try:
        import anthropic

        from src.infrastructure.observability.agent_trace_collector import (
            AgentTraceCollector,
        )

        t0_ms = AgentTraceCollector.offset_ms()
        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        client = anthropic.AsyncAnthropic(**client_kwargs)
        response = await client.messages.create(
            model=model,
            max_tokens=500,
            temperature=0,
            system=_RERANK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        if not response.content:
            logger.warning("rerank.empty_response")
            return chunks[:top_k]
        raw = response.content[0].text.strip()
        logger.info("rerank.raw_response", raw_preview=raw[:500])

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # Parse JSON scores
        scores = json.loads(raw)
        if not isinstance(scores, list):
            logger.warning("rerank.invalid_format", raw=raw[:200])
            return chunks[:top_k]

        # Sort by score descending
        scored = []
        for item in scores:
            idx = item.get("index", -1)
            score = item.get("score", 0)
            if 0 <= idx < len(chunks):
                scored.append((idx, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top_k chunks in reranked order
        result = []
        for idx, score in scored[:top_k]:
            chunk = {**chunks[idx], "_rerank_score": score}
            result.append(chunk)

        # Token-Gov.0: 補 cache token（Anthropic SDK response.usage 提供）
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        cache_creation = (
            getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        )

        end_ms = AgentTraceCollector.offset_ms()
        AgentTraceCollector.add_node(
            node_type="tool_call",
            label=f"rerank ({model.split('-')[1] if '-' in model else model})",
            parent_id=AgentTraceCollector.tool_parent(),
            start_ms=t0_ms,
            end_ms=end_ms,
            token_usage={
                "model": model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_tokens": cache_read,
                "cache_creation_tokens": cache_creation,
            },
            input_chunks=len(chunks),
            output_chunks=len(result),
            top_score=scored[0][1] if scored else 0,
            llm_input=f"[System] {_RERANK_SYSTEM_PROMPT}\n\n[User] {user_prompt}",
            llm_output=raw,
        )

        # Token-Gov.0: 寫進 token_usage_records（與其他 LLM 路徑一致）
        if record_usage and (
            response.usage.input_tokens + response.usage.output_tokens
        ) > 0:
            from src.domain.rag.value_objects import TokenUsage
            from src.domain.usage.category import UsageCategory

            await record_usage.execute(
                tenant_id=tenant_id,
                request_type=UsageCategory.RERANK.value,
                usage=TokenUsage(
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    cache_read_tokens=cache_read,
                    cache_creation_tokens=cache_creation,
                ),
                bot_id=bot_id,
            )

        logger.info(
            "rerank.done",
            model=model,
            input_chunks=len(chunks),
            output_chunks=len(result),
            top_score=scored[0][1] if scored else 0,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read=cache_read,
            cache_creation=cache_creation,
        )
        return result

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("rerank.parse_error", error=str(e))
        return chunks[:top_k]
    except Exception:
        logger.warning("rerank.failed", exc_info=True)
        return chunks[:top_k]
