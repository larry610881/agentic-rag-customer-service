"""設定 snapshot 查詢用例（Issue #60）"""

from __future__ import annotations

from src.domain.observability.effective_config import (
    ConfigSnapshotRepository,
    diff_effective_snapshots,
)
from src.domain.shared.exceptions import EntityNotFoundError


class GetConfigSnapshotUseCase:
    def __init__(self, repository: ConfigSnapshotRepository) -> None:
        self._repo = repository

    async def execute(self, config_hash: str) -> dict:
        found = await self._repo.find_by_hash(config_hash)
        if found is None:
            raise EntityNotFoundError("ConfigSnapshot", config_hash)
        return found


class DiffConfigSnapshotsUseCase:
    def __init__(self, repository: ConfigSnapshotRepository) -> None:
        self._repo = repository

    async def execute(self, hash_a: str, hash_b: str) -> dict:
        a = await self._repo.find_by_hash(hash_a)
        if a is None:
            raise EntityNotFoundError("ConfigSnapshot", hash_a)
        b = await self._repo.find_by_hash(hash_b)
        if b is None:
            raise EntityNotFoundError("ConfigSnapshot", hash_b)
        return {
            "a": hash_a,
            "b": hash_b,
            "changed_fields": diff_effective_snapshots(a["snapshot"], b["snapshot"]),
        }


class GetConfigTimelineUseCase:
    def __init__(self, repository: ConfigSnapshotRepository) -> None:
        self._repo = repository

    async def execute(self, bot_id: str, limit: int = 50) -> list[dict]:
        return await self._repo.timeline_for_bot(bot_id, limit=limit)
