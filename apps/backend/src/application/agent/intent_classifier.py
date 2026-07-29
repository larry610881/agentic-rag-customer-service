"""輕量 LLM 意圖分類器 — 支援 WorkerConfig 和 IntentRoute"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.domain.rag.services import LLMService
from src.domain.usage.category import UsageCategory

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase
    from src.domain.bot.entity import IntentRoute
    from src.domain.bot.worker_config import WorkerConfig

logger = structlog.get_logger(__name__)

_CLASSIFY_SYSTEM_PROMPT = (
    "你是意圖分類器。根據用戶訊息和近期對話，將意圖分類為以下類別之一。\n"
    "只回覆類別名稱，不要加任何其他文字。\n"
    "如果都不符合，回覆「NONE」。"
)

# Issue #51：快速道（direct_retrieval）跳過 ReAct 決策輪後，follow-up 短句
# （「價格呢」）失去 LLM 隱性的 query rewriting → 裸句檢索命中錯誤 chunk。
# 解法：分類與檢索查詢改寫共用同一次 LLM 呼叫（兩行輸出協定），零額外延遲。
_CLASSIFY_REWRITE_SYSTEM_PROMPT = (
    "你是意圖分類器。根據用戶訊息和近期對話，輸出兩行：\n"
    "第一行：將意圖分類為以下類別之一，只輸出類別名稱；"
    "都不符合輸出「NONE」。\n"
    "第二行：檢索查詢 — 把用戶訊息改寫成不依賴上下文也能理解的完整查詢，"
    "補上近期對話中被指代的商品名稱或主題；"
    "若訊息本身已完整，原樣輸出。\n"
    "除這兩行外不要輸出任何其他文字。"
)

# 改寫查詢僅用於向量檢索 embedding；截斷防 LLM 異常輸出污染檢索
_REWRITE_QUERY_MAX_CHARS = 200


def _build_system_with_categories(
    names_and_descriptions: list[tuple[str, str]],
    base_prompt: str = _CLASSIFY_SYSTEM_PROMPT,
) -> str:
    """S-LLM-Cache.1: 把類別列表納入 system prompt，讓 AnthropicLLMService 既有
    cache_control 能 cache 此段（同一 bot 連續分類訊息時命中）。"""
    categories = "\n".join(
        f"- {name}: {desc}" for name, desc in names_and_descriptions
    )
    return f"{base_prompt}\n\n類別：\n{categories}"


def _build_user_message(
    user_message: str,
    router_context: str,
) -> str:
    """純變動部分：對話上下文 + 當下訊息（不進 cache）。"""
    parts = []
    if router_context:
        parts.append(f"近期對話：\n{router_context}")
    parts.append(f"用戶訊息：\n{user_message}")
    return "\n\n".join(parts)


class IntentClassifier:
    """Classify user intent — supports both WorkerConfig and legacy IntentRoute."""

    def __init__(
        self,
        llm_service: LLMService,
        record_usage: "RecordUsageUseCase | None" = None,
    ) -> None:
        self._llm = llm_service
        self._record_usage = record_usage

    async def classify_workers(
        self,
        user_message: str,
        router_context: str,
        workers: list[WorkerConfig],
        router_model: str = "",
        tenant_id: str = "",
        bot_id: str | None = None,
    ) -> WorkerConfig | None:
        """Classify into a WorkerConfig, or None for default fallback."""
        if not workers:
            return None

        names_descs = [
            (w.name, w.description) for w in workers
        ]
        system_prompt = _build_system_with_categories(names_descs)
        user_msg = _build_user_message(user_message, router_context)

        raw = await self._call_llm(
            system_prompt, user_msg,
            [w.name for w in workers], router_model,
            tenant_id=tenant_id, bot_id=bot_id,
        )
        if raw is None:
            return None

        worker_map = {w.name: w for w in workers}
        return self._match(raw, worker_map)

    async def classify_workers_and_rewrite(
        self,
        user_message: str,
        router_context: str,
        workers: list[WorkerConfig],
        router_model: str = "",
        tenant_id: str = "",
        bot_id: str | None = None,
    ) -> tuple[WorkerConfig | None, str]:
        """Issue #51：分類 + 檢索查詢改寫，共用同一次 LLM 呼叫。

        回傳 (worker, 改寫後查詢)。改寫缺失（單行輸出 / LLM 異常）時
        查詢為空字串，呼叫端退回使用者原文 — 行為不劣於現狀。
        """
        if not workers:
            return None, ""

        names_descs = [(w.name, w.description) for w in workers]
        system_prompt = _build_system_with_categories(
            names_descs, base_prompt=_CLASSIFY_REWRITE_SYSTEM_PROMPT
        )
        user_msg = _build_user_message(user_message, router_context)

        raw = await self._call_llm(
            system_prompt, user_msg,
            [w.name for w in workers], router_model,
            tenant_id=tenant_id, bot_id=bot_id,
            # Issue #52：reasoning 模型的 max_completion_tokens 含內部
            # reasoning。已帶 reasoning_effort，此為兜底 —— 若 effort
            # 被 API 拒絕剝除，400 tokens 仍給輕度 reasoning 留空間
            # 讓兩行輸出跑得完；實際可見輸出僅 ~20 tokens 成本不變。
            max_tokens=400,
        )
        # Issue #52 安全網：router 小模型輸出空（reasoning 燒光預算 /
        # 格式全失敗）時，改用預設模型重試一次 —— routing 靜默全滅
        # （每題 fallback 走完整 ReAct）比多付一次分類呼叫昂貴得多。
        if not (raw or "").strip() and router_model:
            logger.warning(
                "intent_classification_router_fallback",
                router_model=router_model,
            )
            raw = await self._call_llm(
                system_prompt, user_msg,
                [w.name for w in workers], "",
                tenant_id=tenant_id, bot_id=bot_id,
                max_tokens=400,
            )
        if raw is None:
            return None, ""

        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            return None, ""
        worker_map = {w.name: w for w in workers}
        matched = self._match(lines[0], worker_map)
        rewritten = (
            lines[1][:_REWRITE_QUERY_MAX_CHARS] if len(lines) > 1 else ""
        )
        return matched, rewritten

    async def classify(
        self,
        user_message: str,
        router_context: str,
        intent_routes: list[IntentRoute],
        tenant_id: str = "",
        bot_id: str | None = None,
    ) -> IntentRoute | None:
        """Legacy: classify into an IntentRoute."""
        if not intent_routes:
            return None

        names_descs = [
            (r.name, r.description) for r in intent_routes
        ]
        system_prompt = _build_system_with_categories(names_descs)
        user_msg = _build_user_message(user_message, router_context)

        raw = await self._call_llm(
            system_prompt, user_msg,
            [r.name for r in intent_routes],
            tenant_id=tenant_id, bot_id=bot_id,
        )
        if raw is None:
            return None

        route_map = {r.name: r for r in intent_routes}
        return self._match(raw, route_map)

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        route_names: list[str],
        router_model: str = "",
        tenant_id: str = "",
        bot_id: str | None = None,
        max_tokens: int = 50,
    ) -> str | None:
        try:
            kwargs: dict[str, Any] = {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "context": "",
                "temperature": 0,
                "max_tokens": max_tokens,
                # Issue #52：分類是簡單任務不需推理。reasoning 模型
                # （gpt-5-nano 等）不壓 reasoning 會把 max_tokens 預算
                # 燒光 → content 空字串 → 靜默 fallback（線上實證）。
                # 值用 'minimal'（gpt-5 家族通用）—— 'none' 實證只有
                # 5.4+tools 收，nano 回 400 被剝除後照樣燒光預算。
                # 非 OpenAI reasoning 模型由各 impl 忽略此 hint。
                "reasoning_effort": "minimal",
            }
            # Use router_model if specified
            if router_model:
                kwargs["model"] = router_model

            result = await self._llm.generate(**kwargs)
            raw = result.text.strip()
            logger.info(
                "intent_classification",
                raw_output=raw,
                routes=route_names,
            )

            # Token-Gov.0: 記錄 intent classify token 用量
            if self._record_usage and result.usage and result.usage.total_tokens > 0:
                await self._record_usage.execute(
                    tenant_id=tenant_id,
                    request_type=UsageCategory.INTENT_CLASSIFY.value,
                    usage=result.usage,
                    bot_id=bot_id,
                )

            return raw
        except Exception:
            logger.warning(
                "intent_classification_failed", exc_info=True
            )
            return None

    @staticmethod
    def _match(raw: str, name_map: dict[str, Any]) -> Any | None:
        """Exact match, then fuzzy substring match."""
        if raw in name_map:
            return name_map[raw]
        for name, item in name_map.items():
            if name in raw:
                return item
        return None
