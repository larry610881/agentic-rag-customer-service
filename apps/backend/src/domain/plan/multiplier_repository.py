"""PlanCategoryMultiplier Repository ABC — Issue #74"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.plan.value_objects import PlanCategoryMultiplier


class PlanCategoryMultiplierRepository(ABC):
    @abstractmethod
    async def list_for_plan(self, plan_id: str) -> list[PlanCategoryMultiplier]: ...

    @abstractmethod
    async def replace_for_plan(
        self, plan_id: str, multipliers: list[PlanCategoryMultiplier]
    ) -> None:
        """整批取代該方案的倍率表（未列出的類別回落方案預設倍率）。"""
        ...
