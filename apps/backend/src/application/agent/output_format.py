"""輸出格式共用決策（Issue #70；channel-parity：web / widget / LINE 同一份）

管線步驟「結構化輸出 / 純文字後處理 / 未命中話術」只能有一份實作，通路端只接收結果：

- ``resolve_structured_llm_params``：依供應商能力等級決定 llm_params 補丁與
  prompt 後綴（A 級傳 response_schema；B 級 response_json_object + schema 進
  prompt；C 級只進 prompt）
- ``finalize_answer``：剝 ``` 圍欄 → json.loads（失敗抓第一個平衡 {...}）→
  schema 驗證；plain_text 剝 Markdown；算出文字通路顯示欄位（output_text_field）
- ``finalize_with_retry``：驗證失敗重試一次（重試呼叫由通路提供），仍失敗回
  未命中話術，並記一個 ``structured_output`` trace 節點
  （status: valid | repaired | fallback | invalid）
- ``resolve_miss_reply``：未命中話術（json 格式時本身必須是 JSON 物件）
- ``retrieval_stats``：快速道 / kb 檢索統計
  （top_score / chunk_count / threshold / miss）
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.domain.bot.entity import (
    DEFAULT_MISS_REPLY,
    DEFAULT_MISS_REPLY_JSON,
    DEFAULT_OUTPUT_TEXT_FIELD,
)
from src.domain.llm.structured_output import (
    JSON_OBJECT,
    NATIVE_SCHEMA,
    capability,
    schema_prompt_block,
    strip_markdown,
    validate_json_output,
)
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

RETRY_INSTRUCTION = (
    "上一次輸出不是合法 JSON 或不符 schema：{error}。請只輸出合法 JSON。"
)


@dataclass(frozen=True)
class OutputSpec:
    """一輪對話生效的輸出設定（bot 欄位 + 生效的供應商 / 模型）。"""

    output_format: str = "text"
    output_schema: dict | None = None
    miss_reply: str = ""
    output_text_field: str = DEFAULT_OUTPUT_TEXT_FIELD
    provider: str = ""
    model: str = ""

    @classmethod
    def from_bot(
        cls, bot: Any, *, provider: str | None = None, model: str | None = None
    ) -> OutputSpec:
        return cls(
            output_format=getattr(bot, "output_format", "text") or "text",
            output_schema=getattr(bot, "output_schema", None) or None,
            miss_reply=getattr(bot, "miss_reply", "") or "",
            output_text_field=(
                getattr(bot, "output_text_field", "") or DEFAULT_OUTPUT_TEXT_FIELD
            ),
            provider=(
                provider if provider is not None else getattr(bot, "llm_provider", "")
            ) or "",
            model=(model if model is not None else getattr(bot, "llm_model", "")) or "",
        )

    @classmethod
    def from_cfg(cls, cfg: dict[str, Any]) -> OutputSpec:
        """web / widget 的 bot_cfg：供應商 / 模型取 worker 覆寫後的生效值。"""
        llm = cfg.get("llm_params") or {}
        return cls(
            output_format=cfg.get("output_format") or "text",
            output_schema=cfg.get("output_schema") or None,
            miss_reply=cfg.get("miss_reply") or "",
            output_text_field=cfg.get("output_text_field") or DEFAULT_OUTPUT_TEXT_FIELD,
            provider=llm.get("provider_name", "") or "",
            model=llm.get("model", "") or "",
        )

    @property
    def is_json(self) -> bool:
        return self.output_format == "json"

    @property
    def is_plain_text(self) -> bool:
        return self.output_format == "plain_text"


@dataclass
class FinalizedAnswer:
    """後處理結果：text 進訊息內容；parsed / display_text 進 structured_content。"""

    text: str
    parsed: dict | None = None
    display_text: str | None = None
    error: str = ""
    status: str = "plain"  # plain | valid | invalid | repaired | fallback | miss

    @property
    def ok(self) -> bool:
        return self.status in ("plain", "valid", "repaired", "miss")


def resolve_structured_llm_params(spec: OutputSpec) -> tuple[dict[str, Any], str]:
    """回 (llm_params 補丁, system prompt 後綴)。非 json 格式為 ({}, "")。"""
    if not spec.is_json:
        return {}, ""
    tier, _ = capability(spec.provider, spec.model)
    if tier == NATIVE_SCHEMA:
        return {"response_schema": spec.output_schema or {"type": "object"}}, ""
    suffix = schema_prompt_block(spec.output_schema)
    if tier == JSON_OBJECT:
        return {"response_json_object": True}, suffix
    return {}, suffix


def append_prompt_suffix(system_prompt: str | None, suffix: str) -> str | None:
    if not suffix:
        return system_prompt
    return f"{system_prompt or ''}\n\n{suffix}"


def _field_text(parsed: dict | None, field: str) -> str:
    if not isinstance(parsed, dict):
        return ""
    value = parsed.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def finalize_answer(
    answer: str,
    output_format: str,
    schema: dict | None,
    output_text_field: str = DEFAULT_OUTPUT_TEXT_FIELD,
) -> FinalizedAnswer:
    """單次後處理（不重試、不記 trace）。json 有效時 text 為正規化 JSON 字串。"""
    if output_format == "json":
        ok, parsed, error = validate_json_output(answer, schema)
        if ok and parsed is not None:
            text = json.dumps(parsed, ensure_ascii=False)
            return FinalizedAnswer(
                text=text,
                parsed=parsed,
                display_text=_field_text(parsed, output_text_field) or text,
                status="valid",
            )
        return FinalizedAnswer(text=answer, error=error, status="invalid")
    if output_format == "plain_text":
        return FinalizedAnswer(text=strip_markdown(answer), status="plain")
    return FinalizedAnswer(text=answer, status="plain")


def resolve_miss_reply(spec: OutputSpec) -> FinalizedAnswer:
    """未命中話術。json：自訂 miss_reply（儲存時已驗證）→ 平台預設物件
    （無 schema 或通過 schema）→ {"answer": DEFAULT_MISS_REPLY}。"""
    if not spec.is_json:
        return FinalizedAnswer(
            text=spec.miss_reply or DEFAULT_MISS_REPLY, status="miss"
        )
    obj: dict | None = None
    if spec.miss_reply:
        ok, parsed, _ = validate_json_output(spec.miss_reply, spec.output_schema)
        if ok:
            obj = parsed
        else:
            # 儲存時已擋非 JSON；此為驗證前既有資料的防禦：包成 {"answer": 文字}
            wrapped = {"answer": spec.miss_reply}
            ok, parsed, _ = validate_json_output(
                json.dumps(wrapped, ensure_ascii=False), spec.output_schema
            )
            obj = parsed if ok else None
    if obj is None:
        ok, parsed, _ = validate_json_output(
            json.dumps(DEFAULT_MISS_REPLY_JSON), spec.output_schema
        )
        obj = parsed if ok else {"answer": DEFAULT_MISS_REPLY}
    return FinalizedAnswer(
        text=json.dumps(obj, ensure_ascii=False),
        parsed=obj,
        display_text=_field_text(obj, spec.output_text_field) or DEFAULT_MISS_REPLY,
        status="miss",
    )


async def finalize_with_retry(
    spec: OutputSpec,
    answer: str,
    retry: Callable[[str], Awaitable[str]] | None = None,
    *,
    fallback: bool = True,
) -> FinalizedAnswer:
    """json：驗證 → 失敗重試一次（retry 收修正指令、回新答案）→ 仍失敗回未命中話術。

    ``fallback=False``（串流：token 已送出）時不以未命中話術取代，僅標記 invalid。
    非 json 格式直接回 finalize_answer 結果。
    """
    fin = finalize_answer(
        answer, spec.output_format, spec.output_schema, spec.output_text_field
    )
    if not spec.is_json:
        return fin
    t0 = AgentTraceCollector.offset_ms()
    status = "valid"
    error = ""
    if fin.status != "valid":
        error = fin.error
        status = "invalid"
        if retry is not None:
            second = await retry(RETRY_INSTRUCTION.format(error=fin.error))
            fin2 = finalize_answer(
                second, spec.output_format, spec.output_schema, spec.output_text_field
            )
            if fin2.status == "valid":
                fin, status, error = fin2, "repaired", ""
            else:
                error = fin2.error
        if status == "invalid" and fallback:
            miss = resolve_miss_reply(spec)
            fin = FinalizedAnswer(
                text=miss.text, parsed=miss.parsed, display_text=miss.display_text,
                error=error, status="fallback",
            )
            status = "fallback"
    label = {
        "valid": "結構化輸出驗證通過",
        "repaired": "結構化輸出重試後通過",
        "fallback": "結構化輸出兩次失敗 → 未命中話術",
        "invalid": "結構化輸出驗證失敗（已串流，保留原文）",
    }[status]
    end = AgentTraceCollector.offset_ms()
    extra: dict[str, Any] = {"status": status}
    if error:
        extra["error"] = error[:500]
    AgentTraceCollector.add_node(
        node_type="structured_output",
        label=label,
        parent_id=None,
        start_ms=t0,
        end_ms=end,
        outcome="success" if status in ("valid", "repaired") else "partial",
        **extra,
    )
    return fin


def merge_usage(first: Any, second: Any) -> None:
    """重試呼叫的 token 用量併入第一次回應（記帳不漏第二次 LLM 呼叫）。"""
    usage2 = getattr(second, "usage", None)
    if usage2 is None:
        return
    usage1 = getattr(first, "usage", None)
    if usage1 is None:
        first.usage = usage2
        return
    from dataclasses import replace as _replace

    first.usage = _replace(
        usage1,
        input_tokens=usage1.input_tokens + usage2.input_tokens,
        output_tokens=usage1.output_tokens + usage2.output_tokens,
        estimated_cost=usage1.estimated_cost + usage2.estimated_cost,
        cache_read_tokens=usage1.cache_read_tokens + usage2.cache_read_tokens,
        cache_creation_tokens=(
            usage1.cache_creation_tokens + usage2.cache_creation_tokens
        ),
    )


def retrieval_stats(plan: Any | None) -> dict[str, Any] | None:
    """快速道 / kb 檢索統計；沒有 plan（完整 ReAct）回 None。"""
    if plan is None:
        return None
    return {
        "top_score": round(float(getattr(plan, "top_score", 0.0) or 0.0), 4),
        "chunk_count": int(getattr(plan, "chunk_count", 0) or 0),
        "threshold": round(float(getattr(plan, "threshold", 0.0) or 0.0), 4),
        "miss": bool(getattr(plan, "miss", False)),
    }
