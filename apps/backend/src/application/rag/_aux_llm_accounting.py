"""輔助 LLM 呼叫（query rewrite / HyDE）的記帳與 trace 節點（Issue #59）

這兩條路徑原本用 ``call_llm`` 直打 provider，既不寫 token_usage_records 也沒有
trace 節點；開啟 rewrite / HyDE 的 bot 成本被低估、瀑布圖也看不到這段時間。
"""

from typing import Any

import structlog

from src.infrastructure.llm.llm_caller import LLMCallResult
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

logger = structlog.get_logger(__name__)


async def account_aux_llm(
    result: LLMCallResult,
    *,
    label: str,
    category: str,
    tenant_id: str,
    record_usage: Any | None,
    start_ms: float,
    llm_input: str,
) -> None:
    token_usage = {
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cache_read_tokens": result.cache_read_tokens,
        "cache_creation_tokens": result.cache_creation_tokens,
    }
    AgentTraceCollector.add_node(
        node_type="tool_call",
        label=label,
        parent_id=AgentTraceCollector.tool_parent(),
        start_ms=start_ms,
        end_ms=AgentTraceCollector.offset_ms(),
        token_usage=token_usage,
        llm_input=llm_input,
        llm_output=result.text,
    )

    if record_usage is None or not tenant_id:
        return
    if result.input_tokens + result.output_tokens <= 0:
        return
    from src.domain.rag.value_objects import TokenUsage

    try:
        await record_usage.execute(
            tenant_id=tenant_id,
            request_type=category,
            usage=TokenUsage(
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_creation_tokens=result.cache_creation_tokens,
            ),
        )
    except Exception:
        logger.warning("aux_llm.usage_record_failed", label=label, exc_info=True)
