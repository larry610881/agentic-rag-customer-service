"""BotConfigVersion repository interface"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.prompt_gate.entity import BotConfigVersion


class BotConfigVersionRepository(ABC):
    @abstractmethod
    async def save(self, version: BotConfigVersion) -> None: ...

    @abstractmethod
    async def find_by_id(
        self, version_id: str, tenant_id: str
    ) -> BotConfigVersion | None:
        """Tenant-scoped 查詢：不屬於該租戶一律回 None。"""
        ...

    @abstractmethod
    async def find_by_bot(
        self,
        bot_id: str,
        tenant_id: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BotConfigVersion]:
        """依 version_no 由新到舊排序。"""
        ...

    @abstractmethod
    async def count_by_bot(
        self, bot_id: str, tenant_id: str, *, status: str | None = None
    ) -> int: ...

    @abstractmethod
    async def find_current(self, bot_id: str) -> BotConfigVersion | None: ...

    @abstractmethod
    async def next_version_no(self, bot_id: str) -> int: ...

    @abstractmethod
    async def revert_validating_to_draft(
        self, version_ids: list[str]
    ) -> int:
        """孤兒清理：把仍卡在 validating 的版本退回 draft。回傳影響列數。"""
        ...

    @abstractmethod
    async def set_current(self, bot_id: str, version_id: str) -> None:
        """單一交易內翻轉 is_current（舊 current 設 False、新版設 True），
        維持 partial unique index 不變量。"""
        ...
