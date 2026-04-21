"""Deduct Tokens Use Case — S-Token-Gov.2 (+.3 auto-topup hook)

從本月 ledger 扣 token：先 base 後 addon，允許 addon 為負（軟上限）。
由 RecordUsageUseCase 在每筆 token usage 寫入後自動 hook。

S-Token-Gov.3：扣完若 addon_remaining ≤ 0 → 觸發 TopupAddonUseCase 自動續約。
- topup_addon + plan_repository 為 optional 依賴（沒注入則純扣費 — 給 unit test 方便）
- topup 失敗以 try/except 容錯，不影響扣費主流程（與 .2 ledger.deduct hook 同模式）
"""

from __future__ import annotations

import logging

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.plan.repository import PlanRepository

logger = logging.getLogger(__name__)


class DeductTokensUseCase:
    def __init__(
        self,
        ledger_repository: TokenLedgerRepository,
        ensure_ledger: EnsureLedgerUseCase,
        topup_addon=None,  # TopupAddonUseCase | None — optional 注入
        plan_repository: PlanRepository | None = None,
    ) -> None:
        self._ledger_repo = ledger_repository
        self._ensure_ledger = ensure_ledger
        self._topup_addon = topup_addon
        self._plan_repo = plan_repository

    async def execute(
        self, *, tenant_id: str, tokens: int, plan_name: str
    ) -> None:
        if tokens <= 0:
            return
        ledger = await self._ensure_ledger.execute(tenant_id, plan_name)
        ledger.deduct(tokens)

        # S-Token-Gov.3: 自動續約觸發條件
        # Token-Gov.7 D (bug 修復): 必須 base 和 addon **都耗盡** 才 topup。
        # 原先只檢查 `addon <= 0` 會在「初始 addon=0（無上月 carryover）」狀況下，
        # 第一次扣費（base 還充足）就觸發 topup，產生虛假計費 (Carrefour 2026-04 實例)。
        triggered_topup = False
        if (
            self._topup_addon is not None
            and self._plan_repo is not None
            and ledger.base_remaining <= 0
            and ledger.addon_remaining <= 0
        ):
            try:
                plan = await self._plan_repo.find_by_name(plan_name)
                if plan is not None:
                    result = await self._topup_addon.execute(
                        ledger=ledger, plan=plan,
                    )
                    if result is not None:
                        # topup 內部已 save 過 ledger，外層不再 save 一次
                        triggered_topup = True
            except Exception:
                logger.warning(
                    "ledger.auto_topup_failed",
                    extra={"tenant_id": tenant_id},
                    exc_info=True,
                )

        if not triggered_topup:
            await self._ledger_repo.save(ledger)
