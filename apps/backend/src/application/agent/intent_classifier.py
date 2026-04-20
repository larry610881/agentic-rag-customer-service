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


def _build_classify_prompt(
    user_message: str,
    router_context: str,
    names_and_descriptions: list[tuple[str, str]],
) -> str:
    categories = "\n".join(
        f"- {name}: {desc}" for name, desc in names_and_descriptions
    )
    parts = [f"類別：\n{categories}"]
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
        prompt = _build_classify_prompt(
            user_message, router_context, names_descs,
        )

        raw = await self._call_llm(
            prompt, [w.name for w in workers], router_model,
            tenant_id=tenant_id, bot_id=bot_id,
        )
        if raw is None:
            return None

        worker_map = {w.name: w for w in workers}
        return self._match(raw, worker_map)

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
        prompt = _build_classify_prompt(
            user_message, router_context, names_descs,
        )

        raw = await self._call_llm(
            prompt, [r.name for r in intent_routes],
            tenant_id=tenant_id, bot_id=bot_id,
        )
        if raw is None:
            return None

        route_map = {r.name: r for r in intent_routes}
        return self._match(raw, route_map)

    async def _call_llm(
        self,
        prompt: str,
        route_names: list[str],
        router_model: str = "",
        tenant_id: str = "",
        bot_id: str | None = None,
    ) -> str | None:
        try:
            kwargs: dict[str, Any] = {
                "system_prompt": _CLASSIFY_SYSTEM_PROMPT,
                "user_message": prompt,
                "context": "",
                "temperature": 0,
                "max_tokens": 50,
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
