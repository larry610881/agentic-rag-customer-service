"""分層設定的 application 共用骨架（Issue #75，自 #68 abuse_settings 抽出）

- ``CachedLayeredProvider``：每租戶解析結果程序內快取 TTL 秒；DB 失效時退回子類別
  決定的 fallback（異常控管 fail-open 退預設、防護階段 fail-safe 全開）。
- ``LayeredSettingsWriter``：platform / profile / tenant 任一層寫入的共用流程——
  沿用既有列 id、存檔、清快取、寫稽核（entity_id = ``<scope_kind>:<scope_id>``）。
各功能只需提供鍵驗證與解析函式。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

import structlog

from src.domain.audit.entity import SOURCE_API
from src.domain.settings.layered import (
    SCOPE_TENANT,
    LayeredSettings,
    LayeredSettingsRepository,
    normalize_scope_id,
    validate_scope_kind,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CachedLayeredProvider(Generic[T]):
    """每個 key（通常是 tenant_id）快取一份解析結果；子類別實作 _load / _fallback。"""

    log_event = "layered_settings.load_failed"

    def __init__(self, repo_factory: Any, ttl_seconds: int = 60) -> None:
        self._repo_factory = repo_factory
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[T, float]] = {}

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    async def resolve(self, key: str) -> T:
        cached = self._cache.get(key)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        try:
            value = await self._load(self._repo_factory(), key)
        except Exception:
            logger.warning(self.log_event, key=key)
            value = self._fallback(key)
        self._cache[key] = (value, time.monotonic() + self._ttl)
        return value

    async def _load(self, repo: Any, key: str) -> T:
        raise NotImplementedError

    def _fallback(self, key: str) -> T:
        raise NotImplementedError


class LayeredSettingsWriter:
    """寫一層設定：驗 scope、沿用既有列、存檔、清快取、寫稽核（鍵驗證由呼叫端先做）。"""

    def __init__(
        self,
        repo: LayeredSettingsRepository,
        entity_cls: type[LayeredSettings],
        audit_entity: str,
        provider: CachedLayeredProvider[Any] | None = None,
        audit: Any | None = None,
    ) -> None:
        self._repo = repo
        self._entity_cls = entity_cls
        self._audit_entity = audit_entity
        self._provider = provider
        self._audit = audit

    async def write(
        self,
        *,
        scope_kind: str,
        scope_id: str,
        overrides: dict[str, Any],
        actor_user_id: str | None,
        source: str = SOURCE_API,
    ) -> Any:
        validate_scope_kind(scope_kind)
        scope_id = normalize_scope_id(scope_kind, scope_id)
        existing = await self._repo.get(scope_kind, scope_id)
        before = dict(existing.overrides) if existing else {}
        settings = self._entity_cls(
            scope_kind=scope_kind,
            scope_id=scope_id,
            overrides=dict(overrides),
            updated_by=actor_user_id,
            updated_at=datetime.now(timezone.utc),
            **({"id": existing.id} if existing else {}),
        )
        await self._repo.save(settings)
        if self._provider is not None:
            # 租戶層只影響該租戶；平台 / 方案層影響所有租戶
            self._provider.invalidate(None if scope_kind != SCOPE_TENANT else scope_id)
        if self._audit is not None:
            await self._audit.record(
                entity_type=self._audit_entity,
                entity_id=f"{scope_kind}:{scope_id}",
                action="update",
                before=before,
                after=dict(overrides),
                actor_user_id=actor_user_id,
                tenant_id=scope_id if scope_kind == SCOPE_TENANT else None,
                source=source,
            )
        return settings
