"""租戶額度用盡策略覆寫 — Issue #74

- system_admin 可對任何租戶覆寫。
- tenant_admin 只能改自己的租戶，且方案必須 `tenant_may_change_policy=True`，
  否則 `PermissionError`（router 對應 403）。
- 任何切換寫稽核（entity_type `tenant_billing`）、清計價脈絡與預檢快取。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.billing.exhaustion import effective_policy, resolve_block_message
from src.domain.plan.entity import ExhaustionPolicy
from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.domain.tenant.repository import TenantRepository

AUDIT_ENTITY = "tenant_billing"
SYSTEM_ADMIN_ROLE = "system_admin"


@dataclass(frozen=True)
class TenantBillingPolicyView:
    tenant_id: str
    exhaustion_policy_override: str | None
    block_message_override: str | None
    effective_policy: str
    block_message: str
    tenant_may_change_policy: bool


class UpdateTenantBillingPolicyUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        plan_repository: PlanRepository,
        billing_context: Any | None = None,
        quota_preflight: Any | None = None,
        audit: Any | None = None,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._plan_repo = plan_repository
        self._billing_context = billing_context
        self._quota_preflight = quota_preflight
        self._audit = audit

    async def execute(
        self,
        *,
        tenant_id: str,
        exhaustion_policy: str | None,
        block_message: str | None,
        actor_role: str | None,
        actor_user_id: str | None,
    ) -> TenantBillingPolicyView:
        if (
            exhaustion_policy is not None
            and exhaustion_policy not in ExhaustionPolicy.ALL
        ):
            raise ValidationError(
                "exhaustion_policy must be one of "
                f"{sorted(ExhaustionPolicy.ALL)} or null"
            )
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)
        plan = await self._plan_repo.find_by_name(tenant.plan)
        may_change = bool(plan.tenant_may_change_policy) if plan else False
        if actor_role != SYSTEM_ADMIN_ROLE and not may_change:
            raise PermissionError("此方案不允許租戶自行變更額度用盡策略")

        before = {
            "exhaustion_policy_override": tenant.exhaustion_policy_override,
            "block_message_override": tenant.block_message_override,
        }
        tenant.exhaustion_policy_override = exhaustion_policy
        tenant.block_message_override = (
            block_message.strip() if block_message and block_message.strip() else None
        )
        await self._tenant_repo.save(tenant)

        if self._billing_context is not None:
            self._billing_context.invalidate(tenant_id)
        if self._quota_preflight is not None:
            await self._quota_preflight.invalidate(tenant_id)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=tenant_id,
                action="update",
                before=before,
                after={
                    "exhaustion_policy_override": tenant.exhaustion_policy_override,
                    "block_message_override": tenant.block_message_override,
                },
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )
        return TenantBillingPolicyView(
            tenant_id=tenant_id,
            exhaustion_policy_override=tenant.exhaustion_policy_override,
            block_message_override=tenant.block_message_override,
            effective_policy=effective_policy(
                plan.exhaustion_policy if plan else None,
                tenant.exhaustion_policy_override,
            ),
            block_message=resolve_block_message(
                tenant.block_message_override,
                plan.block_message if plan else None,
            ),
            tenant_may_change_policy=may_change,
        )
