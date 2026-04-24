"""Topup Addon Use Case — S-Ledger-Unification P4 + Tier 1 T1.1

當 addon 耗盡時觸發：寫一筆 token_ledger_topups append-only 紀錄 +
一筆 BillingTransaction。POC plan (addon_pack_tokens=0) 視為「不續約」直接回 None。

本 use case 不負責「決定何時 trigger」— 上游（RecordUsageUseCase
auto-topup hook）判斷後才呼叫。本層只負責「執行 topup 並落帳」。

### P4 變更 vs S-Token-Gov.3 原版

- 舊版：mutate `ledger.addon_remaining`（mutable state）
- 新版：寫 `token_ledger_topups` append-only row（addon_remaining 改由
  ComputeTenantQuotaUseCase 從 SUM(topups) - overage 即時算）

### Tier 1 T1.1 修復（Issue #42）

- P4 原本 `ledger_id=""`，違反 `billing_transactions_ledger_id_fkey` FK constraint
  → 每次 auto_topup 寫 BillingTransaction 都 FK violation，被 try/except 吞
  → 金流審計斷層
- 修法：注入 `ledger_repository`，execute 時 fetch ledger 拿真實 id
"""

from __future__ import annotations

from src.domain.billing.entity import (
    TRANSACTION_TYPE_AUTO_TOPUP,
    TRIGGERED_BY_SYSTEM,
    BillingTransaction,
)
from src.domain.billing.repository import BillingTransactionRepository
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.ledger.topup_entity import REASON_AUTO_TOPUP, TokenLedgerTopup
from src.domain.ledger.topup_repository import TokenLedgerTopupRepository
from src.domain.plan.entity import Plan


class TopupAddonUseCase:
    def __init__(
        self,
        topup_repository: TokenLedgerTopupRepository,
        billing_transaction_repository: BillingTransactionRepository,
        ledger_repository: TokenLedgerRepository,
    ) -> None:
        self._topup_repo = topup_repository
        self._billing_repo = billing_transaction_repository
        self._ledger_repo = ledger_repository

    async def execute(
        self,
        *,
        tenant_id: str,
        cycle_year_month: str,
        plan: Plan,
    ) -> BillingTransaction | None:
        """補 addon 一個 pack 並寫入交易紀錄。

        Returns:
            BillingTransaction on success；plan.addon_pack_tokens<=0 時回 None；
            找不到 ledger（理論上不會發生 — 上游 auto-topup hook 已確保 ledger 存在）
            時亦回 None（defensive）
        """
        if plan.addon_pack_tokens <= 0:
            return None

        # T1.1: fetch ledger to get real id for FK compliance
        ledger = await self._ledger_repo.find_by_tenant_and_cycle(
            tenant_id, cycle_year_month
        )
        if ledger is None:
            # Defensive — auto-topup hook 在 ensure_ledger 之後才呼叫，
            # ledger 不存在代表呼叫方時序錯亂，不寫任何東西避免 orphan topup
            return None

        topup = TokenLedgerTopup(
            tenant_id=tenant_id,
            cycle_year_month=cycle_year_month,
            amount=plan.addon_pack_tokens,
            reason=REASON_AUTO_TOPUP,
        )
        await self._topup_repo.save(topup)

        tx = BillingTransaction(
            tenant_id=tenant_id,
            ledger_id=ledger.id,
            cycle_year_month=cycle_year_month,
            plan_name=plan.name,
            transaction_type=TRANSACTION_TYPE_AUTO_TOPUP,
            addon_tokens_added=plan.addon_pack_tokens,
            amount_currency=plan.currency,
            amount_value=plan.addon_price,
            triggered_by=TRIGGERED_BY_SYSTEM,
            reason=f"auto_topup +{plan.addon_pack_tokens}",
        )
        await self._billing_repo.save(tx)
        return tx
