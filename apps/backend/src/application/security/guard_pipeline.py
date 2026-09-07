"""防護階段管線閘門（Issue #75）— web / widget / LINE 共用的一份

通路轉接器（send_message / handle_webhook）每回合取一次 ``EffectiveGuard``，之後每段防護
都經由這裡決定「跑不跑」：

- ``regex_input``       → PromptGuardService.check_input
- ``classifier_attack`` → 分類器 is_attack（fast / deep 沿用分流那次呼叫；kb 模式不帶
                          worker 只做攻擊判定）
- ``output_guard``      → PromptGuardService.check_output（含咽喉點）
- ``abuse_scoring``     → P7 evaluate / record
- ``local_classifier``  → 預留，no-op

未注入 provider（舊接線 / 測試）時退回全部階段開啟，行為與 #75 之前一致。
"""

from __future__ import annotations

from typing import Any

import structlog

from src.domain.security.guard_stages import (
    ALL_STAGES_ON,
    STAGE_ABUSE_SCORING,
    STAGE_CLASSIFIER_ATTACK,
    STAGE_OUTPUT_GUARD,
    STAGE_REGEX_INPUT,
    EffectiveGuard,
)
from src.domain.shared.exceptions import ValidationError
from src.infrastructure.observability.agent_trace_collector import AgentTraceCollector

logger = structlog.get_logger(__name__)

METADATA_KEY = "_guard_stages"   # agent metadata：咽喉點依此跳過關閉的階段
TRACE_NODE_TYPE = "guard_stages"


def stages_from_metadata(metadata: dict[str, Any] | None) -> list[str] | None:
    """咽喉點用：metadata 未帶清單 → None（= 舊行為，全部跑）。"""
    stages = (metadata or {}).get(METADATA_KEY)
    return list(stages) if isinstance(stages, (list, tuple)) else None


class GuardPipeline:
    """把「有效階段 → 各段防護呼叫」的判斷收斂在一處；通路端只拿結果。"""

    def __init__(
        self,
        prompt_guard: Any | None,
        guard_provider: Any | None = None,
        intent_classifier: Any | None = None,
    ) -> None:
        self._prompt_guard = prompt_guard
        self._provider = guard_provider
        self._classifier = intent_classifier

    # ── 解析 ──

    async def effective(self, tenant_id: str, bot: Any = None) -> EffectiveGuard:
        if self._provider is None:
            return ALL_STAGES_ON
        effective: EffectiveGuard = await self._provider.effective_for(tenant_id, bot)
        return effective

    @staticmethod
    def overlay_bot(guard: EffectiveGuard, bot: Any) -> EffectiveGuard:
        """bot 層疊加（只加不減；鎖定時忽略）。bot 存了未知階段 → 忽略 bot 層。"""
        stages = getattr(bot, "guard_stages", None) if bot is not None else None
        if not isinstance(stages, list):
            return guard
        try:
            return guard.with_bot(stages)
        except ValidationError:
            logger.warning("guard_stages.bot_override_invalid", stages=stages)
            return guard

    @staticmethod
    def annotate(guard: EffectiveGuard, metadata: dict[str, Any] | None = None) -> None:
        """trace 節點（有效階段 + 來源）＋ agent metadata（咽喉點讀）。"""
        if metadata is not None:
            metadata[METADATA_KEY] = list(guard.stages)
        try:
            now_ms = AgentTraceCollector.offset_ms()
            AgentTraceCollector.add_node(
                node_type=TRACE_NODE_TYPE,
                label="防護階段",
                parent_id=None,
                start_ms=now_ms,
                end_ms=now_ms,
                stages=list(guard.stages),
                sources=guard.sources,
                required=list(guard.required),
                locked=guard.locked,
            )
        except Exception:
            logger.debug("guard_stages.trace_add_failed", exc_info=True)

    # ── 各階段閘門 ──

    def abuse_enabled(self, guard: EffectiveGuard) -> bool:
        return guard.enabled(STAGE_ABUSE_SCORING)

    def regex_input_enabled(self, guard: EffectiveGuard) -> bool:
        """LINE 通路要把 check_input 包成並行 task，先問一次要不要建。"""
        return self._prompt_guard is not None and guard.enabled(STAGE_REGEX_INPUT)

    def classifier_attack(self, guard: EffectiveGuard, is_attack: bool) -> bool:
        """fast / deep：分流那次呼叫已產出 is_attack；階段關閉時忽略。"""
        return bool(is_attack) and guard.enabled(STAGE_CLASSIFIER_ATTACK)

    async def kb_attack_check(
        self,
        guard: EffectiveGuard,
        *,
        message: str,
        router_context: str,
        router_model: str = "",
        tenant_id: str = "",
        bot_id: str | None = None,
        test_mode: bool = False,
    ) -> bool:
        """kb 模式：不分流、不帶 worker，只做攻擊判定（階段關閉 → 不呼叫小模型）。"""
        if not guard.enabled(STAGE_CLASSIFIER_ATTACK) or self._classifier is None:
            return False
        t0 = AgentTraceCollector.offset_ms()
        outcome = await self._classifier.classify_sanitize(
            user_message=message,
            router_context=router_context,
            workers=[],
            router_model=router_model,
            tenant_id=tenant_id,
            bot_id=bot_id,
            test_mode=test_mode,
            attack_only=True,
        )
        AgentTraceCollector.add_node(
            node_type="intent_classify",
            label="攻擊判定（kb 模式，不分流）",
            parent_id=None,
            start_ms=t0,
            end_ms=AgentTraceCollector.offset_ms(),
            attack=bool(outcome.is_attack),
            classifier_model=router_model,
        )
        return bool(outcome.is_attack)

    async def check_input(
        self,
        guard: EffectiveGuard,
        message: str,
        *,
        tenant_id: str,
        bot_id: str | None,
        user_id: str | None,
        dry_run: bool = False,
    ) -> Any | None:
        """regex 輸入防護；階段關閉或未接 guard → None（視同通過）。"""
        if self._prompt_guard is None or not guard.enabled(STAGE_REGEX_INPUT):
            return None
        return await self._prompt_guard.check_input(
            message, tenant_id=tenant_id, bot_id=bot_id, user_id=user_id,
            dry_run=dry_run,
        )

    async def block_by_classifier(
        self,
        guard: EffectiveGuard,
        *,
        message: str,
        tenant_id: str,
        bot_id: str | None,
        user_id: str | None,
        dry_run: bool = False,
    ) -> Any | None:
        if self._prompt_guard is None or not guard.enabled(STAGE_CLASSIFIER_ATTACK):
            return None
        return await self._prompt_guard.block_by_classifier(
            message=message, tenant_id=tenant_id, bot_id=bot_id, user_id=user_id,
            dry_run=dry_run,
        )

    async def check_output(
        self,
        guard: EffectiveGuard,
        response: str,
        *,
        tenant_id: str,
        bot_id: str | None,
        user_id: str | None,
        user_message: str,
        dry_run: bool = False,
    ) -> Any | None:
        """輸出防護；階段關閉、未接 guard 或空回覆 → None（視同通過）。"""
        if (
            self._prompt_guard is None
            or not response
            or not guard.enabled(STAGE_OUTPUT_GUARD)
        ):
            return None
        return await self._prompt_guard.check_output(
            response, tenant_id=tenant_id, bot_id=bot_id, user_id=user_id,
            user_message=user_message, dry_run=dry_run,
        )
