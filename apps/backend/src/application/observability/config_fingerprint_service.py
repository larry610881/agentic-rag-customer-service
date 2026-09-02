"""設定指紋紀錄器（Issue #60）

use case 在 prompt 組裝完成時呼叫 ``record(effective)``：算 hash、程序內 LRU
已見過就直接回；否則 ``ensure``（冪等）寫入 config_snapshots。任何錯誤
fail-open：指紋仍回傳給 trace / usage 打標，只是 snapshot 可能晚點才寫進去。
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import structlog

from src.domain.observability.effective_config import (
    SNAPSHOT_SCHEMA,
    ConfigSnapshotRepository,
    EffectiveConfig,
)

logger = structlog.get_logger(__name__)


class ConfigFingerprintService:
    def __init__(
        self,
        repository: ConfigSnapshotRepository | None = None,
        session_factory: Any | None = None,
        cache_size: int = 512,
    ) -> None:
        self._repo = repository
        self._session_factory = session_factory
        self._cache_size = cache_size
        self._seen: OrderedDict[str, None] = OrderedDict()

    def _remember(self, config_hash: str) -> bool:
        """回 True 表示第一次看到。"""
        if config_hash in self._seen:
            self._seen.move_to_end(config_hash)
            return False
        self._seen[config_hash] = None
        if len(self._seen) > self._cache_size:
            self._seen.popitem(last=False)
        return True

    async def _ensure(self, config_hash: str, snapshot: dict) -> None:
        if self._repo is not None:
            await self._repo.ensure(config_hash, snapshot, SNAPSHOT_SCHEMA)
            return
        if self._session_factory is None:
            return
        from src.infrastructure.db.repositories.config_snapshot_repository import (
            SQLAlchemyConfigSnapshotRepository,
        )

        async with self._session_factory() as session:
            await SQLAlchemyConfigSnapshotRepository(session).ensure(
                config_hash, snapshot, SNAPSHOT_SCHEMA
            )

    async def record(self, effective: EffectiveConfig) -> str:
        config_hash = effective.fingerprint()
        if not self._remember(config_hash):
            return config_hash
        try:
            await self._ensure(config_hash, effective.to_snapshot())
        except Exception:
            # 下次再試：從 LRU 移除，避免這個 hash 永遠不落庫
            self._seen.pop(config_hash, None)
            logger.warning(
                "config_fingerprint.persist_failed",
                config_hash=config_hash[:12],
                exc_info=True,
            )
        return config_hash
