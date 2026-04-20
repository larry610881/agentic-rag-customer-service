"""Quota Email Dispatch Use Case — S-Token-Gov.3.5

由 worker cron 每天觸發：掃 quota_alert_logs.delivered_to_email=False，
找對應 tenant 的 admin email，渲染 template 寄出，標 delivered。

容錯策略：
- 無 admin email → 仍 mark_delivered（避免無限重試空 alert）
- SendGrid 寄送失敗 → 不 mark，下次 cron 再重試
"""

from __future__ import annotations

import logging

from src.application.billing._email_templates import render_quota_alert_email
from src.domain.auth.repository import UserRepository
from src.domain.billing.email_sender import QuotaAlertEmailSender
from src.domain.billing.quota_alert import QuotaAlertLogRepository
from src.domain.tenant.repository import TenantRepository

logger = logging.getLogger(__name__)


class QuotaEmailDispatchUseCase:
    def __init__(
        self,
        alert_repository: QuotaAlertLogRepository,
        tenant_repository: TenantRepository,
        user_repository: UserRepository,
        email_sender: QuotaAlertEmailSender,
        dashboard_url: str = "http://localhost:5174/quota",
    ) -> None:
        self._alert_repo = alert_repository
        self._tenant_repo = tenant_repository
        self._user_repo = user_repository
        self._email_sender = email_sender
        self._dashboard_url = dashboard_url

    async def execute(self) -> dict[str, int]:
        unsent = await self._alert_repo.find_undelivered(limit=100)
        stats = {
            "scanned": 0,
            "sent": 0,
            "skipped_no_email": 0,
            "failed": 0,
        }

        # 預先 fetch 所有 tenants（避免 N+1）
        tenants = await self._tenant_repo.find_all()
        tenant_by_id = {t.id.value: t for t in tenants}

        for alert in unsent:
            stats["scanned"] += 1
            tenant = tenant_by_id.get(alert.tenant_id)
            if tenant is None:
                # 租戶被刪 — 標 delivered 避免重試
                logger.warning(
                    "quota_email.tenant_missing",
                    extra={"alert_id": alert.id, "tenant_id": alert.tenant_id},
                )
                await self._alert_repo.mark_delivered(alert.id)
                stats["skipped_no_email"] += 1
                continue

            admin_email = await self._user_repo.find_admin_email_by_tenant(
                alert.tenant_id
            )
            if not admin_email:
                logger.warning(
                    "quota_email.no_admin_email",
                    extra={
                        "alert_id": alert.id,
                        "tenant_id": alert.tenant_id,
                        "tenant_name": tenant.name,
                    },
                )
                await self._alert_repo.mark_delivered(alert.id)
                stats["skipped_no_email"] += 1
                continue

            try:
                subject, text_body, html_body = render_quota_alert_email(
                    alert, tenant, dashboard_url=self._dashboard_url,
                )
                await self._email_sender.send(
                    to_email=admin_email,
                    to_name=tenant.name,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
                await self._alert_repo.mark_delivered(alert.id)
                stats["sent"] += 1
            except Exception:
                logger.warning(
                    "quota_email.send_failed",
                    extra={"alert_id": alert.id, "to": admin_email},
                    exc_info=True,
                )
                stats["failed"] += 1
                # 不 mark — 下次 cron 重試

        logger.info("quota_email_dispatch.done", extra={"stats": stats})
        return stats
