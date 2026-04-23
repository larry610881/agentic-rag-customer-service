"""Update Tenant Use Case — S-Token-Gov.1 (+ Bug 2 fix: sentinel pattern)

既有 tenant_router PATCH /config 直接操作 repo，違反 application 層編排原則。
本 use case 集中處理 tenant 設定更新。

## included_categories 三態語意（Bug 2 修復）

| command 值              | 行為                              |
|-------------------------|-----------------------------------|
| 不傳（default = _UNSET）| 保持 tenant 既有值不變            |
| 顯式 None               | 重置為 NULL（= 全計入 safe default） |
| list（含 []）           | 明確寫入（[] = 全不計入 POC 免計費）  |

其他 optional 欄位（plan / monthly_token_limit / default_*_model）同樣適用。
router 應透過 Pydantic `model_fields_set` 判斷 client 是否顯式傳入。
"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository

# Sentinel 用於區分「client 未傳」vs「client 顯式傳 None」。
# module-level singleton，不可序列化也不可 compare 相等（除了 identity）。
_UNSET: Any = object()


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_id: str
    # 所有 optional 欄位 default = _UNSET。`is _UNSET` 比較判斷「有沒有傳」。
    plan: Any = field(default=_UNSET)
    monthly_token_limit: Any = field(default=_UNSET)
    included_categories: Any = field(default=_UNSET)
    default_ocr_model: Any = field(default=_UNSET)
    default_context_model: Any = field(default=_UNSET)
    default_classification_model: Any = field(default=_UNSET)
    # S-KB-Followup.2: intent_classify / conversation_summary 的 tenant default
    default_summary_model: Any = field(default=_UNSET)
    default_intent_model: Any = field(default=_UNSET)


class UpdateTenantUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        plan_repository: PlanRepository | None = None,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._plan_repo = plan_repository

    async def execute(self, command: UpdateTenantCommand) -> Tenant:  # noqa: C901
        tenant = await self._tenant_repo.find_by_id(command.tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", command.tenant_id)

        # plan 變更時驗證存在 + active
        if command.plan is not _UNSET and command.plan != tenant.plan:
            if self._plan_repo:
                plan = await self._plan_repo.find_by_name(command.plan)
                if plan is None:
                    raise EntityNotFoundError("Plan", command.plan)
                if not plan.is_active:
                    raise DomainException(
                        f"Plan '{command.plan}' is inactive and cannot be assigned"
                    )
            tenant.plan = command.plan

        if command.monthly_token_limit is not _UNSET:
            tenant.monthly_token_limit = command.monthly_token_limit
        if command.included_categories is not _UNSET:
            tenant.included_categories = command.included_categories
        if command.default_ocr_model is not _UNSET:
            tenant.default_ocr_model = command.default_ocr_model
        if command.default_context_model is not _UNSET:
            tenant.default_context_model = command.default_context_model
        if command.default_classification_model is not _UNSET:
            tenant.default_classification_model = (
                command.default_classification_model
            )
        if command.default_summary_model is not _UNSET:
            tenant.default_summary_model = command.default_summary_model
        if command.default_intent_model is not _UNSET:
            tenant.default_intent_model = command.default_intent_model

        await self._tenant_repo.save(tenant)
        return tenant
