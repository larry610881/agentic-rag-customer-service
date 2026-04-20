"""Deduct Tokens Use Case — S-Token-Gov.2

從本月 ledger 扣 token：先 base 後 addon，允許 addon 為負（軟上限）。
由 RecordUsageUseCase 在每筆 token usage 寫入後自動 hook。
"""

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.ledger.repository import TokenLedgerRepository


class DeductTokensUseCase:
    def __init__(
        self,
        ledger_repository: TokenLedgerRepository,
        ensure_ledger: EnsureLedgerUseCase,
    ) -> None:
        self._ledger_repo = ledger_repository
        self._ensure_ledger = ensure_ledger

    async def execute(
        self, *, tenant_id: str, tokens: int, plan_name: str
    ) -> None:
        if tokens <= 0:
            return
        ledger = await self._ensure_ledger.execute(tenant_id, plan_name)
        ledger.deduct(tokens)
        await self._ledger_repo.save(ledger)
