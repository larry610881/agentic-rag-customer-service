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
    async def create_next_version(
        self, version: BotConfigVersion
    ) -> BotConfigVersion:
        """M2：取號 + INSERT 併入重試迴圈，並發撞唯一約束時重取號重試，
        多次失敗才拋 VersionConflictError（→409）。回傳含 version_no 的版本。"""
        ...

    @abstractmethod
    async def save_status_transition(
        self, version: BotConfigVersion, *, expected_status: str, action: str
    ) -> None:
        """M3/M6：條件式狀態轉移（樂觀鎖）。以讀取時狀態為 WHERE 條件更新，
        並發已改動（rowcount=0）時拋 InvalidVersionTransitionError（→409）。"""
        ...

    @abstractmethod
    async def revert_stale_validating_versions(self) -> int:
        """M5：revert 所有 validating 且對應 gate_run 非 running/queued（或無 run）
        的版本。撈回 mark_orphans_error 漏掉的孤兒（run 已 completed 但版本仍卡
        validating）。回傳影響列數。"""
        ...

    @abstractmethod
    async def set_current(self, bot_id: str, version_id: str) -> None:
        """單一交易內翻轉 is_current（舊 current 設 False、新版設 True），
        維持 partial unique index 不變量。"""
        ...
