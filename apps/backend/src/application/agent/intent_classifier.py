"""輕量 LLM 意圖分類器 — 只在 bot.intent_routes 非空時啟用"""

import structlog

from src.domain.bot.entity import IntentRoute
from src.domain.rag.services import LLMService

logger = structlog.get_logger(__name__)

_CLASSIFY_SYSTEM_PROMPT = (
    "你是意圖分類器。根據用戶訊息和近期對話，將意圖分類為以下類別之一。\n"
    "只回覆類別名稱，不要加任何其他文字。\n"
    "如果都不符合，回覆「NONE」。"
)


def _build_classify_prompt(
    user_message: str,
    router_context: str,
    intent_routes: list[IntentRoute],
) -> str:
    """Build the user-facing classification prompt."""
    categories = "\n".join(
        f"- {r.name}: {r.description}" for r in intent_routes
    )
    parts = [f"類別：\n{categories}"]
    if router_context:
        parts.append(f"近期對話：\n{router_context}")
    parts.append(f"用戶訊息：\n{user_message}")
    return "\n\n".join(parts)


class IntentClassifier:
    """Classify user intent based on bot-configured intent routes."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def classify(
        self,
        user_message: str,
        router_context: str,
        intent_routes: list[IntentRoute],
    ) -> IntentRoute | None:
        """Return the matched IntentRoute, or None for fallback."""
        if not intent_routes:
            return None

        prompt = _build_classify_prompt(
            user_message, router_context, intent_routes,
        )

        try:
            result = await self._llm.generate(
                system_prompt=_CLASSIFY_SYSTEM_PROMPT,
                user_message=prompt,
                context="",
                temperature=0,
                max_tokens=50,
            )
            raw = result.text.strip()
            logger.info(
                "intent_classification",
                raw_output=raw,
                routes=[r.name for r in intent_routes],
            )

            # Match against route names
            route_map = {r.name: r for r in intent_routes}
            if raw in route_map:
                return route_map[raw]

            # Fuzzy: check if raw output contains any route name
            for name, route in route_map.items():
                if name in raw:
                    return route

        except Exception:
            logger.warning("intent_classification_failed", exc_info=True)

        return None
