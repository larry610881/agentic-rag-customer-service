"""Plan Repository ABC"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.plan.entity import Plan


class PlanRepository(ABC):
    @abstractmethod
    async def save(self, plan: Plan) -> Plan:
        """新增或更新（依 id upsert）"""
        ...

    @abstractmethod
    async def find_by_id(self, plan_id: str) -> Plan | None: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Plan | None: ...

    @abstractmethod
    async def find_all(self, *, include_inactive: bool = True) -> list[Plan]: ...

    @abstractmethod
    async def delete(self, plan_id: str) -> None:
        """硬刪 — caller 須先驗證無租戶綁定，否則會 orphan"""
        ...

    @abstractmethod
    async def count_tenants_using_plan(self, plan_name: str) -> int:
        """查有多少租戶綁定此 plan name — 給軟/硬刪判斷使用"""
        ...
