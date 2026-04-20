"""List Quota Events Use Case — S-Token-Gov.3

合併 BillingTransaction + QuotaAlertLog 為單一時間軸事件，給 admin UI
`/admin/quota-events` 頁列表。

策略：
- 兩表分別查 limit*2（多取一些防 merge 後不夠）
- application 層按 created_at desc merge
- limit/offset 套在 merged 結果上
- 補 tenant_name（從 tenant_repo 一次查）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from src.domain.billing.repository import BillingTransactionRepository
from src.domain.billing.quota_alert import QuotaAlertLogRepository
from src.domain.tenant.repository import TenantRepository


@dataclass(frozen=True)
class QuotaEventItem:
    event_id: str
    event_type: str  # 'auto_topup' | 'base_warning_80' | 'base_exhausted_100'
    tenant_id: str
    tenant_name: str
    cycle_year_month: str
    created_at: datetime
    # auto_topup 專用
    addon_tokens_added: int | None = None
    amount_currency: str | None = None
    amount_value: Decimal | None = None
    # alert 專用
    used_ratio: Decimal | None = None
    message: str | None = None
    reason: str | None = None
    # S-Token-Gov.3.5: alert 是否已寄出 email（auto_topup 為 None）
    delivered_to_email: bool | None = None
    extra: dict = field(default_factory=dict)


class ListQuotaEventsUseCase:
    def __init__(
        self,
        billing_transaction_repository: BillingTransactionRepository,
        alert_repository: QuotaAlertLogRepository,
        tenant_repository: TenantRepository,
    ) -> None:
        self._billing_repo = billing_transaction_repository
        self._alert_repo = alert_repository
        self._tenant_repo = tenant_repository

    async def execute(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[QuotaEventItem], int]:
        # 取兩表，over-fetch limit+offset 數量以保證 merge 後仍有 limit
        fetch_window = limit + offset
        billing_txs = await self._billing_repo.list_recent(
            limit=fetch_window, offset=0, tenant_id=tenant_id,
        )
        alerts = await self._alert_repo.list_recent(
            limit=fetch_window, offset=0, tenant_id=tenant_id,
        )

        # 補 tenant_name 字典（一次查全部）
        tenants = await self._tenant_repo.find_all()
        name_by_id = {t.id.value: t.name for t in tenants}

        items: list[QuotaEventItem] = []
        for tx in billing_txs:
            items.append(
                QuotaEventItem(
                    event_id=tx.id,
                    event_type=tx.transaction_type,
                    tenant_id=tx.tenant_id,
                    tenant_name=name_by_id.get(tx.tenant_id, ""),
                    cycle_year_month=tx.cycle_year_month,
                    created_at=tx.created_at,
                    addon_tokens_added=tx.addon_tokens_added,
                    amount_currency=tx.amount_currency,
                    amount_value=tx.amount_value,
                    reason=tx.reason or None,
                )
            )
        for alert in alerts:
            items.append(
                QuotaEventItem(
                    event_id=alert.id,
                    event_type=alert.alert_type,
                    tenant_id=alert.tenant_id,
                    tenant_name=name_by_id.get(alert.tenant_id, ""),
                    cycle_year_month=alert.cycle_year_month,
                    created_at=alert.created_at,
                    used_ratio=alert.used_ratio,
                    message=alert.message or None,
                    delivered_to_email=alert.delivered_to_email,
                )
            )

        items.sort(key=lambda i: i.created_at, reverse=True)
        # 套用 offset + limit
        sliced = items[offset:offset + limit]

        # total = 兩表 count 加總（一致性折衷：跨兩表精確 distinct count 太貴；事件 id 不會碰撞）
        total_billing = await self._billing_repo.count_recent(tenant_id=tenant_id)
        total_alert = await self._alert_repo.count_recent(tenant_id=tenant_id)
        total = total_billing + total_alert

        return sliced, total
