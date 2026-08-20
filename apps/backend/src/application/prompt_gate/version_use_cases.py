"""Bot 設定版本 use cases：create / list / get / publish / reject / rollback

發布（PublishVersionUseCase）是唯一寫入 bots 表白名單欄位的通道（spec §1）：
手動編輯、優化器產出、回朔全部收斂到這裡，含 cache invalidation。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from src.application.prompt_gate.static_checks import check_prompt_fields
from src.domain.bot.repository import BotRepository
from src.domain.prompt_gate.config_snapshot import (
    PROMPT_FIELDS,
    SNAPSHOT_FIELDS,
    SNAPSHOT_SCHEMA,
    apply_snapshot,
    diff_snapshots,
    take_snapshot,
)
from src.domain.prompt_gate.entity import (
    SOURCE_MANUAL,
    SOURCE_ROLLBACK,
    STATUS_PUBLISHED,
    VERDICT_SKIPPED,
    BotConfigVersion,
)
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.shared.cache_service import CacheService
from src.domain.shared.exceptions import (
    EntityNotFoundError,
    ValidationError,
)


def _changed_prompt_fields(snapshot: dict, changed: list[str]) -> dict[str, str]:
    return {
        f: snapshot.get(f, "") for f in PROMPT_FIELDS if f in changed
    }


@dataclass(frozen=True)
class CreateConfigVersionCommand:
    tenant_id: str
    bot_id: str
    changes: dict  # 白名單欄位的部分更新（key 必須 ∈ SNAPSHOT_FIELDS）
    author_user_id: str | None = None
    source: str = SOURCE_MANUAL
    source_run_id: str | None = None


class CreateConfigVersionUseCase:
    """建立 draft：現行快照 ⊕ changes → 靜態檢查 → 存版本列。
    檢查失敗不產生版本（spec §4.2）。"""

    def __init__(
        self,
        bot_repository: BotRepository,
        version_repository: BotConfigVersionRepository,
    ) -> None:
        self._bot_repo = bot_repository
        self._version_repo = version_repository

    async def execute(
        self, command: CreateConfigVersionCommand
    ) -> BotConfigVersion:
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None or bot.tenant_id != command.tenant_id:
            raise EntityNotFoundError("Bot", command.bot_id)

        unknown = set(command.changes) - set(SNAPSHOT_FIELDS)
        if unknown:
            raise ValidationError(
                f"非白名單欄位不可版本化: {sorted(unknown)}"
            )

        current = take_snapshot(bot)
        candidate = copy.deepcopy(current)
        for key, value in command.changes.items():
            if key == "llm_params":
                candidate["llm_params"] = {
                    **candidate["llm_params"],
                    **(value or {}),
                }
            else:
                candidate[key] = value

        changed = diff_snapshots(current, candidate)
        if not changed:
            raise ValidationError("no_changes: 設定與現行版本相同")

        check_prompt_fields(_changed_prompt_fields(candidate, changed))

        version = BotConfigVersion(
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            version_no=await self._version_repo.next_version_no(
                command.bot_id
            ),
            config_snapshot=candidate,
            snapshot_schema=SNAPSHOT_SCHEMA,
            changed_fields=changed,
            source=command.source,
            source_run_id=command.source_run_id,
            author_user_id=command.author_user_id,
        )
        await self._version_repo.save(version)
        return version


class ListConfigVersionsUseCase:
    def __init__(
        self, version_repository: BotConfigVersionRepository
    ) -> None:
        self._version_repo = version_repository

    async def execute(
        self,
        tenant_id: str,
        bot_id: str,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[BotConfigVersion], int]:
        versions = await self._version_repo.find_by_bot(
            bot_id, tenant_id, status=status, limit=limit, offset=offset
        )
        total = await self._version_repo.count_by_bot(
            bot_id, tenant_id, status=status
        )
        return versions, total


class GetConfigVersionUseCase:
    def __init__(
        self, version_repository: BotConfigVersionRepository
    ) -> None:
        self._version_repo = version_repository

    async def execute(
        self, tenant_id: str, version_id: str
    ) -> BotConfigVersion:
        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        return version


class PublishConfigVersionUseCase:
    """發布：唯一寫入 bots 白名單欄位的通道。
    overlay 套用快照 → save bot → 翻轉 is_current → 清 cache。
    Phase A（閘門未上）：一律 verdict=skipped 直接發布。"""

    def __init__(
        self,
        bot_repository: BotRepository,
        version_repository: BotConfigVersionRepository,
        cache_service: CacheService | None = None,
    ) -> None:
        self._bot_repo = bot_repository
        self._version_repo = version_repository
        self._cache = cache_service

    async def execute(
        self,
        tenant_id: str,
        version_id: str,
        *,
        verdict: str = VERDICT_SKIPPED,
    ) -> BotConfigVersion:
        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None:
            raise EntityNotFoundError("BotConfigVersion", version_id)

        bot = await self._bot_repo.find_by_id(version.bot_id)
        if bot is None or bot.tenant_id != tenant_id:
            raise EntityNotFoundError("Bot", version.bot_id)

        version.mark_published(verdict)  # 非法轉移在此 raise

        apply_snapshot(bot, version.config_snapshot)
        await self._bot_repo.save(bot)
        await self._version_repo.save(version)
        await self._version_repo.set_current(version.bot_id, version.id)

        if self._cache is not None:
            await self._cache.delete(f"bot:{bot.id.value}")
            await self._cache.delete(f"bot:sc:{bot.short_code.value}")
        return version


class RejectConfigVersionUseCase:
    def __init__(
        self, version_repository: BotConfigVersionRepository
    ) -> None:
        self._version_repo = version_repository

    async def execute(
        self, tenant_id: str, version_id: str
    ) -> BotConfigVersion:
        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        version.mark_rejected()
        await self._version_repo.save(version)
        return version


@dataclass(frozen=True)
class RollbackConfigVersionCommand:
    tenant_id: str
    bot_id: str
    target_version_id: str
    author_user_id: str | None = None


class RollbackConfigVersionUseCase:
    """回朔：複製歷史 published 快照建新版本 → 免重驗直接發布（定案 9）。
    overlay 合併語意（定案 12）由 apply_snapshot 保證。"""

    def __init__(
        self,
        bot_repository: BotRepository,
        version_repository: BotConfigVersionRepository,
        publish_use_case: PublishConfigVersionUseCase,
    ) -> None:
        self._bot_repo = bot_repository
        self._version_repo = version_repository
        self._publish = publish_use_case

    async def execute(
        self, command: RollbackConfigVersionCommand
    ) -> BotConfigVersion:
        target = await self._version_repo.find_by_id(
            command.target_version_id, command.tenant_id
        )
        if target is None or target.bot_id != command.bot_id:
            raise EntityNotFoundError(
                "BotConfigVersion", command.target_version_id
            )
        if target.status != STATUS_PUBLISHED:
            raise ValidationError(
                "rollback_target_not_published: 回朔目標必須是曾發布的版本"
            )

        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None or bot.tenant_id != command.tenant_id:
            raise EntityNotFoundError("Bot", command.bot_id)

        changed = diff_snapshots(
            take_snapshot(bot), target.config_snapshot
        )
        if not changed:
            raise ValidationError("no_changes: 目標版本與現行設定相同")

        version = BotConfigVersion(
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            version_no=await self._version_repo.next_version_no(
                command.bot_id
            ),
            config_snapshot=copy.deepcopy(target.config_snapshot),
            snapshot_schema=target.snapshot_schema,
            changed_fields=changed,
            source=SOURCE_ROLLBACK,
            source_run_id=target.id,  # 記錄回朔來源版本
            author_user_id=command.author_user_id,
        )
        await self._version_repo.save(version)
        return await self._publish.execute(
            command.tenant_id, version.id, verdict=VERDICT_SKIPPED
        )
