"""租戶設定變更通知偏好（Issue #77）

租戶勾選「哪些欄位群組變更要通知」（model / prompt / knowledge / tools / guard）：
- `None` = 平台預設（model + prompt）；`[]` = 完全關閉。
- tenant_admin 只能改自己的租戶（否則 `PermissionError`，router 對應 403）；
  system_admin 可改任一租戶。
- 每次寫入留稽核（entity_type `tenant_notification`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.observability.config_change import (
    GROUP_LABELS,
    GROUP_ORDER,
    effective_notify_groups,
    validate_notify_groups,
)
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.domain.tenant.repository import TenantRepository

AUDIT_ENTITY = "tenant_notification"
SYSTEM_ADMIN_ROLE = "system_admin"


@dataclass(frozen=True)
class NotifyGroupOption:
    key: str
    label: str


@dataclass(frozen=True)
class TenantNotificationPreferencesView:
    tenant_id: str
    fields: list[str] | None        # 租戶設定值（None = 平台預設）
    effective: list[str]            # 生效清單
    available_groups: list[NotifyGroupOption]


def _view(
    tenant_id: str, configured: list[str] | None
) -> TenantNotificationPreferencesView:
    return TenantNotificationPreferencesView(
        tenant_id=tenant_id,
        fields=list(configured) if configured is not None else None,
        effective=effective_notify_groups(configured),
        available_groups=[
            NotifyGroupOption(key=g, label=GROUP_LABELS[g]) for g in GROUP_ORDER
        ],
    )


class GetTenantNotificationPreferencesUseCase:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self._tenant_repo = tenant_repository

    async def execute(self, *, tenant_id: str) -> TenantNotificationPreferencesView:
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)
        return _view(tenant_id, tenant.config_change_notify_fields)


class UpdateTenantNotificationPreferencesUseCase:
    def __init__(
        self, tenant_repository: TenantRepository, audit: Any | None = None
    ) -> None:
        self._tenant_repo = tenant_repository
        self._audit = audit

    async def execute(
        self,
        *,
        tenant_id: str,
        groups: list[str] | None,
        actor_role: str | None,
        actor_tenant_id: str | None,
        actor_user_id: str | None,
    ) -> TenantNotificationPreferencesView:
        if actor_role != SYSTEM_ADMIN_ROLE and actor_tenant_id != tenant_id:
            raise PermissionError(
                "Cannot change other tenant's notification preferences"
            )
        try:
            clean = validate_notify_groups(groups)
        except ValueError as e:
            raise ValidationError(str(e)) from None
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)

        before = {"config_change_notify_fields": tenant.config_change_notify_fields}
        tenant.config_change_notify_fields = clean
        await self._tenant_repo.save(tenant)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=tenant_id,
                action="update",
                before=before,
                after={"config_change_notify_fields": clean},
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )
        return _view(tenant_id, clean)
