"""Topup Addon Use Case — S-Token-Gov.3

當 ledger.addon_remaining ≤ 0 時觸發：補一個 plan.addon_pack_tokens 並寫入
BillingTransaction。POC plan (addon_pack_tokens=0) 視為「不續約」直接回 None。

注意：本 use case 不負責「決定何時 trigger」— 上游（DeductTokensUseCase）
判斷後才呼叫。本層只負責「執行 topup 並落帳」。
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.billing.entity import (
    TRANSACTION_TYPE_AUTO_TOPUP,
    TRIGGERED_BY_SYSTEM,
    BillingTransaction,
)
from src.domain.billing.repository import BillingTransactionRepository
from src.domain.ledger.entity import TokenLedger
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.plan.entity import Plan


class TopupAddonUseCase:
    def __init__(
        self,
        ledger_repository: TokenLedgerRepository,
        billing_transaction_repository: BillingTransactionRepository,
    ) -> None:
        self._ledger_repo = ledger_repository
        self._billing_repo = billing_transaction_repository

    async def execute(
        self,
        *,
        ledger: TokenLedger,
        plan: Plan,
    ) -> tuple[TokenLedger, BillingTransaction] | None:
        """補 addon 一個 pack 並寫入交易紀錄。

        Returns:
            (ledger, tx) on success；plan.addon_pack_tokens<=0 時回 None
        """
        if plan.addon_pack_tokens <= 0:
            return None

        before = ledger.addon_remaining
        ledger.addon_remaining += plan.addon_pack_tokens
        ledger.updated_at = datetime.now(timezone.utc)
        await self._ledger_repo.save(ledger)

        tx = BillingTransaction(
            tenant_id=ledger.tenant_id,
            ledger_id=ledger.id,
            cycle_year_month=ledger.cycle_year_month,
            plan_name=ledger.plan_name,
            transaction_type=TRANSACTION_TYPE_AUTO_TOPUP,
            addon_tokens_added=plan.addon_pack_tokens,
            amount_currency=plan.currency,
            amount_value=plan.addon_price,
            triggered_by=TRIGGERED_BY_SYSTEM,
            reason=f"addon_remaining={before} → topup +{plan.addon_pack_tokens}",
        )
        await self._billing_repo.save(tx)
        return ledger, tx
