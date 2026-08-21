"""PromptGateRun repository interface"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.prompt_gate.gate_run_entity import PromptGateRun


class PromptGateRunRepository(ABC):
    @abstractmethod
    async def save(self, run: PromptGateRun) -> None: ...

    @abstractmethod
    async def find_by_id(
        self, run_id: str, tenant_id: str
    ) -> PromptGateRun | None:
        """Tenant-scoped 查詢。"""
        ...

    @abstractmethod
    async def count_today(self, bot_id: str) -> int:
        """該 bot 今日（UTC）已啟動的 run 數（日限額用）。"""
        ...

    @abstractmethod
    async def mark_orphans_error(
        self, *, grace_minutes: int = 30
    ) -> list[str]:
        """啟動時清孤兒：status ∈ {queued, running} 且 created_at 超過
        grace_minutes → error（M7：寬限窗避免殺掉其他實例剛啟動的健康 run）。
        回傳被標記 run 的 version_id 清單（供把 validating 版本退回 draft）。"""
        ...
