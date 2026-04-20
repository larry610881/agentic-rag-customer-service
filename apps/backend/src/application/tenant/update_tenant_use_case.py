"""Update Tenant Use Case — S-Token-Gov.1（補既有 DDD 違反）

既有 tenant_router PATCH /config 直接操作 repo，違反 application 層編排原則。
本 use case 集中處理 tenant 設定更新，含 S-Token-Gov.1 加入的 plan 欄位。
"""

from dataclasses import dataclass

from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_id: str
    plan: str | None = None
    monthly_token_limit: int | None = None
    # S-Token-Gov.2: included_categories
    # 慣例：None = 不變更（保持既有值，含預設 NULL）；list = 明確寫入
    # 故 admin 第一次勾選 → 寫入 list；想「全不計入」傳 []
    # 想設回「全計入」(NULL) — 本 sprint 不支援，未來加 reset 端點
    included_categories: list[str] | None = None
    default_ocr_model: str | None = None
    default_context_model: str | None = None
    default_classification_model: str | None = None


class UpdateTenantUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        plan_repository: PlanRepository | None = None,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._plan_repo = plan_repository

    async def execute(self, command: UpdateTenantCommand) -> Tenant:
        tenant = await self._tenant_repo.find_by_id(command.tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", command.tenant_id)

        # plan 變更時驗證存在 + active
        if command.plan is not None and command.plan != tenant.plan:
            if self._plan_repo:
                plan = await self._plan_repo.find_by_name(command.plan)
                if plan is None:
                    raise EntityNotFoundError("Plan", command.plan)
                if not plan.is_active:
                    raise DomainException(
                        f"Plan '{command.plan}' is inactive and cannot be assigned"
                    )
            tenant.plan = command.plan

        if command.monthly_token_limit is not None:
            tenant.monthly_token_limit = command.monthly_token_limit
        if command.included_categories is not None:
            tenant.included_categories = command.included_categories
        if command.default_ocr_model is not None:
            tenant.default_ocr_model = command.default_ocr_model
        if command.default_context_model is not None:
            tenant.default_context_model = command.default_context_model
        if command.default_classification_model is not None:
            tenant.default_classification_model = command.default_classification_model

        await self._tenant_repo.save(tenant)
        return tenant
