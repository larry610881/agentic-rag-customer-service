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
    STATUS_DRAFT,
    STATUS_PENDING_PUBLISH,
    STATUS_PUBLISHED,
    VERDICT_FAIL,
    VERDICT_FORCED,
    VERDICT_PASS,
    VERDICT_SKIPPED,
    BotConfigVersion,
    GateBlockedError,
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
            config_snapshot=candidate,
            snapshot_schema=SNAPSHOT_SCHEMA,
            changed_fields=changed,
            source=command.source,
            source_run_id=command.source_run_id,
            author_user_id=command.author_user_id,
        )
        # M2：取號與 INSERT 併入 repo 的重試迴圈（並發撞唯一約束時重取號重試，
        # 多次失敗轉 409），取代先前「MAX+1 取號後獨立 save」的競態。
        return await self._version_repo.create_next_version(version)


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
    Phase C 閘門分支（spec §4.1 / gate_run_lifecycle.feature）：
      gate 未啟用（tenant flag off 或 gate_mode=off）→ skipped 直接發布
      pending_publish（驗證通過）→ pass 發布（定案 1=B 人工按發布）
      block + draft（fail/未驗）→ 409（force 無效）
      warn  + draft(fail) + force → forced 發布；未帶 force → 409"""

    def __init__(
        self,
        bot_repository: BotRepository,
        version_repository: BotConfigVersionRepository,
        cache_service: CacheService | None = None,
        tenant_repository=None,
    ) -> None:
        self._bot_repo = bot_repository
        self._version_repo = version_repository
        self._cache = cache_service
        self._tenant_repo = tenant_repository

    async def _gate_active(self, bot) -> bool:
        if bot.gate_mode == "off" or self._tenant_repo is None:
            return False
        tenant = await self._tenant_repo.find_by_id(bot.tenant_id)
        return bool(tenant and getattr(tenant, "prompt_gate_enabled", False))

    @staticmethod
    def _resolve_gate_verdict(
        version: BotConfigVersion, gate_mode: str, force: bool
    ) -> str:
        if version.status == STATUS_PENDING_PUBLISH:
            return VERDICT_PASS
        if version.status == STATUS_DRAFT:
            if (
                gate_mode == "warn"
                and force
                and version.gate_verdict == VERDICT_FAIL
            ):
                return VERDICT_FORCED
            raise GateBlockedError(
                "閘門未通過：draft 需先送驗且通過"
                + ("；warn 模式可帶 force=true 強制發布" if gate_mode == "warn" else "")
            )
        # 其餘狀態交給 mark_published 的轉移 guard
        return VERDICT_PASS

    async def execute(
        self,
        tenant_id: str,
        version_id: str,
        *,
        verdict: str = VERDICT_SKIPPED,
        force: bool = False,
        expected_bot_id: str | None = None,
    ) -> BotConfigVersion:
        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        # L1：URL 的 bot_id 與版本實際歸屬須一致，否則以 bot A 的 URL 可發布
        # bot B 的版本（同租戶），audit/前端呈現與作用對象脫鉤。
        if expected_bot_id is not None and version.bot_id != expected_bot_id:
            raise EntityNotFoundError("BotConfigVersion", version_id)

        bot = await self._bot_repo.find_by_id(version.bot_id)
        if bot is None or bot.tenant_id != tenant_id:
            raise EntityNotFoundError("Bot", version.bot_id)

        # H1：rollback 是回朔到「曾發布且驗過」的快照，定案 9 免重驗直接發布。
        # 不得走 gate 判定，否則 gate 啟用（warn/block）時 rollback 的 draft 版本
        # 會被 _resolve_gate_verdict 一律擋下（409）——最需要緊急回朔的環境反而不可用。
        if version.source != SOURCE_ROLLBACK and await self._gate_active(bot):
            verdict = self._resolve_gate_verdict(
                version, bot.gate_mode, force
            )

        prev_status = version.status
        version.mark_published(verdict)  # 非法轉移在此 raise（記憶體 guard）

        # M3：先以樂觀鎖搶下 status 轉移（WHERE status=prev_status）。並發的
        # publish/reject 只有一方 rowcount=1，輸的一方在此 409，不會先污染 bot 設定。
        await self._version_repo.save_status_transition(
            version, expected_status=prev_status, action="publish"
        )
        apply_snapshot(bot, version.config_snapshot)
        await self._bot_repo.save(bot)
        # set_current 在單一交易內先清舊 current 再設新，是 is_current 的唯一翻轉點
        # （mark_published 不再預設 True，避免 save 先 commit 撞 ix_bcv_current，C1）
        await self._version_repo.set_current(version.bot_id, version.id)
        version.is_current = True  # 回傳實體反映 DB 翻轉結果

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
        self,
        tenant_id: str,
        version_id: str,
        *,
        expected_bot_id: str | None = None,
    ) -> BotConfigVersion:
        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        # L1：URL bot_id 與版本歸屬一致性（同 publish）
        if expected_bot_id is not None and version.bot_id != expected_bot_id:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        prev_status = version.status
        version.mark_rejected()
        # M3：條件式轉移，並發 publish 已搶先發布時此處 409（而非無條件覆寫成
        # rejected，留下 status=rejected 但 is_current=TRUE 的不一致）。
        await self._version_repo.save_status_transition(
            version, expected_status=prev_status, action="reject"
        )
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


class GetVersionMetricsUseCase:
    """版本服役成效（spec §13.6 層次 1）：tenant scoping 由 version 查詢保證。"""

    def __init__(
        self,
        version_repository: BotConfigVersionRepository,
        metrics_repository,
    ) -> None:
        self._version_repo = version_repository
        self._metrics_repo = metrics_repository

    async def execute(
        self,
        tenant_id: str,
        version_id: str,
        *,
        expected_bot_id: str | None = None,
    ):
        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        # L1：URL bot_id 與版本歸屬一致性
        if expected_bot_id is not None and version.bot_id != expected_bot_id:
            raise EntityNotFoundError("BotConfigVersion", version_id)
        return await self._metrics_repo.get_metrics(tenant_id, version_id)
