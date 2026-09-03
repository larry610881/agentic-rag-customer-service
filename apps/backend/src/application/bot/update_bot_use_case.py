"""更新機器人用例"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from src.application.bot._tenant_guard import ensure_bot_tenant
from src.application.prompt_gate.static_checks import check_prompt_fields
from src.domain.bot.entity import (
    VALID_BOT_MODES,
    Bot,
    BotMcpBinding,
    IntentRoute,
    McpServerConfig,
    McpToolMeta,
    ToolRagConfig,
)
from src.domain.bot.repository import BotRepository
from src.domain.platform.services import EncryptionService
from src.domain.prompt_gate.config_snapshot import (
    PROMPT_FIELDS,
    SNAPSHOT_SCHEMA,
    diff_snapshots,
    take_snapshot,
)
from src.domain.prompt_gate.entity import (
    SOURCE_MANUAL,
    VERDICT_SKIPPED,
    BotConfigVersion,
    GateBlockedError,
)
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.rag.retrieval_mode import normalize_modes, validate_modes
from src.domain.shared.cache_service import CacheService
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError

_UNSET = object()

# 前端送回此遮罩值表示「保留原加密值」
_MASKED_VALUE = "***"


@dataclass(frozen=True)
class UpdateBotCommand:
    bot_id: str
    # 歸屬檢查用（C9）：由 router 從 JWT 帶入，非可版本化的 bot 欄位
    tenant_id: str | None = None
    role: str | None = None
    # Issue #60：稽核 actor（同時補進 bot_config_versions.author_user_id）
    actor_user_id: str | None = None
    name: object = _UNSET
    description: object = _UNSET
    is_active: object = _UNSET
    knowledge_base_ids: object = _UNSET
    bot_prompt: object = _UNSET
    temperature: object = _UNSET
    max_tokens: object = _UNSET
    history_limit: object = _UNSET
    frequency_penalty: object = _UNSET
    reasoning_effort: object = _UNSET
    rag_top_k: object = _UNSET
    rag_score_threshold: object = _UNSET
    enabled_tools: object = _UNSET
    llm_provider: object = _UNSET
    llm_model: object = _UNSET
    show_sources: object = _UNSET
    eval_provider: object = _UNSET
    eval_model: object = _UNSET
    eval_depth: object = _UNSET
    gate_mode: object = _UNSET
    mode: object = _UNSET  # Issue #66：fast | deep
    gate_soft_threshold: object = _UNSET
    gate_repeats: object = _UNSET
    gate_auto_publish: object = _UNSET
    gate_daily_limit: object = _UNSET
    gate_budget_usd: object = _UNSET
    gate_excluded_cases: object = _UNSET
    mcp_servers: object = _UNSET
    mcp_bindings: object = _UNSET
    max_tool_calls: object = _UNSET
    base_prompt: object = _UNSET
    widget_enabled: object = _UNSET
    widget_allowed_origins: object = _UNSET
    widget_keep_history: object = _UNSET
    widget_welcome_message: object = _UNSET
    widget_placeholder_text: object = _UNSET
    widget_greeting_messages: object = _UNSET
    widget_greeting_animation: object = _UNSET
    memory_enabled: object = _UNSET
    memory_extraction_threshold: object = _UNSET
    memory_extraction_prompt: object = _UNSET
    rerank_enabled: object = _UNSET
    rerank_model: object = _UNSET
    rerank_top_n: object = _UNSET
    # Issue #43 — Bot-level RAG retrieval modes
    rag_retrieval_modes: object = _UNSET
    query_rewrite_enabled: object = _UNSET
    query_rewrite_model: object = _UNSET
    query_rewrite_extra_hint: object = _UNSET
    hyde_enabled: object = _UNSET
    hyde_model: object = _UNSET
    hyde_extra_hint: object = _UNSET
    tool_configs: object = _UNSET
    customer_service_url: object = _UNSET
    intent_routes: object = _UNSET
    router_model: object = _UNSET
    busy_reply_message: object = _UNSET
    line_channel_secret: object = _UNSET
    line_channel_access_token: object = _UNSET
    line_show_sources: object = _UNSET


class UpdateBotUseCase:
    def __init__(
        self,
        bot_repository: BotRepository,
        cache_service: CacheService | None = None,
        encryption_service: EncryptionService | None = None,
        version_repository: BotConfigVersionRepository | None = None,
        tenant_repository=None,
        eval_dataset_repository=None,
        audit: Any | None = None,
    ) -> None:
        self._bot_repo = bot_repository
        self._cache_service = cache_service
        self._encryption = encryption_service
        self._version_repo = version_repository
        self._tenant_repo = tenant_repository
        self._eval_dataset_repo = eval_dataset_repository
        # Issue #60：管理端變更稽核（None 時不記）
        self._audit = audit

    @staticmethod
    def _apply_updates(bot: Bot, command: UpdateBotCommand) -> None:
        """Apply non-_UNSET fields from command to bot entity."""
        if command.mode is not _UNSET and command.mode not in VALID_BOT_MODES:
            raise ValidationError(
                f"mode must be one of {list(VALID_BOT_MODES)}"
            )
        _DIRECT_FIELDS = (
            "name", "description", "is_active",
            "bot_prompt",
            "llm_provider", "llm_model", "show_sources",
            "eval_provider", "eval_model", "eval_depth",
            "gate_mode", "gate_soft_threshold", "gate_repeats",
            "mode",
            "gate_auto_publish", "gate_daily_limit", "gate_budget_usd",
            "max_tool_calls",
            "widget_enabled", "widget_keep_history",
            "widget_welcome_message", "widget_placeholder_text",
            "widget_greeting_animation",
            "base_prompt",
            "memory_enabled", "memory_extraction_threshold",
            "memory_extraction_prompt",
            "busy_reply_message",
            "line_channel_secret", "line_channel_access_token",
            "line_show_sources",
        )
        for field in _DIRECT_FIELDS:
            val = getattr(command, field)
            if val is _UNSET:
                continue
            # M23：LINE 憑證 API 回應為 "***" 遮罩，表單原封送回時視為未變更
            # （比照 mcp env_values 慣例）；要清除請送空字串。
            if (
                field in ("line_channel_secret", "line_channel_access_token")
                and val == _MASKED_VALUE
            ):
                continue
            setattr(bot, field, val)

        if command.knowledge_base_ids is not _UNSET:
            bot.knowledge_base_ids = list(command.knowledge_base_ids)  # type: ignore[arg-type]
        if command.enabled_tools is not _UNSET:
            bot.enabled_tools = list(command.enabled_tools)  # type: ignore[arg-type]
        if command.widget_allowed_origins is not _UNSET:
            bot.widget_allowed_origins = list(command.widget_allowed_origins)  # type: ignore[arg-type]
        if command.widget_greeting_messages is not _UNSET:
            bot.widget_greeting_messages = list(command.widget_greeting_messages)  # type: ignore[arg-type]
        if command.gate_excluded_cases is not _UNSET:
            bot.gate_excluded_cases = list(command.gate_excluded_cases)  # type: ignore[arg-type]
        if command.rerank_enabled is not _UNSET:
            bot.rerank_enabled = command.rerank_enabled  # type: ignore[assignment]
        if command.rerank_model is not _UNSET:
            bot.rerank_model = command.rerank_model  # type: ignore[assignment]
        if command.rerank_top_n is not _UNSET:
            bot.rerank_top_n = command.rerank_top_n  # type: ignore[assignment]
        # Issue #43 — Bot-level RAG retrieval modes
        if command.rag_retrieval_modes is not _UNSET:
            modes = list(command.rag_retrieval_modes)  # type: ignore[arg-type]
            try:
                validate_modes(modes)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            bot.rag_retrieval_modes = normalize_modes(modes)
        if command.query_rewrite_enabled is not _UNSET:
            bot.query_rewrite_enabled = command.query_rewrite_enabled  # type: ignore[assignment]
        if command.query_rewrite_model is not _UNSET:
            bot.query_rewrite_model = command.query_rewrite_model  # type: ignore[assignment]
        if command.query_rewrite_extra_hint is not _UNSET:
            bot.query_rewrite_extra_hint = command.query_rewrite_extra_hint  # type: ignore[assignment]
        if command.hyde_enabled is not _UNSET:
            bot.hyde_enabled = command.hyde_enabled  # type: ignore[assignment]
        if command.hyde_model is not _UNSET:
            bot.hyde_model = command.hyde_model  # type: ignore[assignment]
        if command.hyde_extra_hint is not _UNSET:
            bot.hyde_extra_hint = command.hyde_extra_hint  # type: ignore[assignment]
        if command.tool_configs is not _UNSET:
            bot.tool_configs = {
                name: ToolRagConfig(
                    rag_top_k=cfg.get("rag_top_k"),
                    rag_score_threshold=cfg.get("rag_score_threshold"),
                    rerank_enabled=cfg.get("rerank_enabled"),
                    rerank_model=cfg.get("rerank_model"),
                    rerank_top_n=cfg.get("rerank_top_n"),
                    kb_ids=cfg.get("kb_ids"),
                )
                for name, cfg in (command.tool_configs or {}).items()  # type: ignore[union-attr]
                if isinstance(cfg, dict)
            }
        if command.customer_service_url is not _UNSET:
            bot.customer_service_url = command.customer_service_url  # type: ignore[assignment]
        if command.intent_routes is not _UNSET:
            bot.intent_routes = [
                IntentRoute(
                    name=r.get("name", ""),
                    description=r.get("description", ""),
                    system_prompt=r.get("system_prompt", ""),
                )
                for r in command.intent_routes  # type: ignore[union-attr]
            ]
        if command.router_model is not _UNSET:
            bot.router_model = command.router_model  # type: ignore[assignment]
        if command.mcp_servers is not _UNSET:
            bot.mcp_servers = [
                McpServerConfig(
                    url=s.get("url", ""),
                    name=s.get("name", ""),
                    enabled_tools=s.get("enabled_tools", []),
                    tools=[
                        McpToolMeta(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                        )
                        for t in s.get("tools", [])
                    ],
                    version=s.get("version", ""),
                )
                for s in command.mcp_servers  # type: ignore[union-attr]
            ]

        # mcp_bindings is handled separately (needs encryption + masking)

        # LLM params — collect changed fields, apply once
        _LLM_FIELDS = (
            "temperature", "max_tokens", "history_limit",
            "frequency_penalty", "reasoning_effort",
            "rag_top_k", "rag_score_threshold",
        )
        llm_changes = {
            k: getattr(command, k)
            for k in _LLM_FIELDS
            if getattr(command, k) is not _UNSET
        }
        if llm_changes:
            bot.llm_params = replace(bot.llm_params, **llm_changes)

    def _encrypt_bindings(
        self,
        new_bindings: list[dict],
        old_bindings_map: dict[str, BotMcpBinding],
    ) -> list[BotMcpBinding]:
        """Encrypt env_values, preserving masked (***) values from existing bindings."""
        result: list[BotMcpBinding] = []
        for b in new_bindings:
            registry_id = b.get("registry_id", "")
            old_binding = old_bindings_map.get(registry_id)
            old_env = old_binding.env_values if old_binding else {}

            raw_env = b.get("env_values", {})
            encrypted_env: dict[str, str] = {}
            for k, v in raw_env.items():
                if not v or v == _MASKED_VALUE:
                    # Keep existing encrypted value
                    encrypted_env[k] = old_env.get(k, "")
                elif self._encryption:
                    encrypted_env[k] = self._encryption.encrypt(v)
                else:
                    encrypted_env[k] = v

            result.append(
                BotMcpBinding(
                    registry_id=registry_id,
                    enabled_tools=b.get("enabled_tools", []),
                    env_values=encrypted_env,
                )
            )
        return result

    async def _gate_active(self, bot: Bot) -> bool:
        """三層開關的前兩層：tenant flag AND bot gate_mode ≠ off。
        依賴未注入時視為關閉（向後相容）。"""
        if bot.gate_mode == "off" or self._tenant_repo is None:
            return False
        tenant = await self._tenant_repo.find_by_id(bot.tenant_id)
        return bool(tenant and getattr(tenant, "prompt_gate_enabled", False))

    async def _ensure_dataset_bound(self, bot: Bot) -> None:
        """啟用前置條件（spec §2.1）：自訂集（非平台通用集）至少 1 個
        啟用案例，否則 gate_mode 不可 ≠ off。"""
        if self._eval_dataset_repo is None:
            return
        datasets = await self._eval_dataset_repo.find_by_bot(
            bot.id.value, bot.tenant_id
        )
        has_enabled_case = any(
            not d.is_platform_base
            and any(tc.enabled for tc in d.test_cases)
            for d in datasets
        )
        if not has_enabled_case:
            raise ValidationError(
                "gate_mode 啟用前須先設定問題集"
                "（該 bot 至少要綁 1 個含啟用案例的自訂題集）"
            )

    @staticmethod
    def _audit_view(bot: Bot) -> dict:
        """Issue #60：稽核視圖 = 版控白名單 + 不進快照但影響行為/治理的欄位。"""
        view = dict(take_snapshot(bot))
        view["name"] = bot.name
        view["description"] = getattr(bot, "description", "")
        view["intent_routes"] = list(getattr(bot, "intent_routes", []) or [])
        for f in (
            "gate_mode", "gate_soft_threshold", "gate_repeats", "gate_auto_publish",
            "gate_daily_limit", "gate_budget_usd", "eval_depth", "show_sources",
            "line_show_sources",
        ):
            if hasattr(bot, f):
                view[f] = getattr(bot, f)
        return view

    async def _record_config_version(
        self, bot: Bot, before_snapshot: dict, actor_user_id: str | None = None
    ) -> None:
        """PUT /bots 版控墊片（spec §13.4）：白名單欄位有變更時——
        gate 未啟用 → 透明產生 published 版本列（verdict=skipped）；
        gate 啟用（warn/block）→ 409 導引版本 API（Phase C）。
        非版控欄位（外觀/憑證/營運/治理）變更不產生版本。"""
        if self._version_repo is None:
            return
        after = take_snapshot(bot)
        changed = diff_snapshots(before_snapshot, after)
        if not changed:
            return
        if await self._gate_active(bot):
            raise GateBlockedError(
                "發布閘門啟用中：受版控欄位"
                f"（{', '.join(changed)}）的變更請走版本 API "
                "POST /api/v1/bots/{bot_id}/config-versions"
            )
        # 第 0 層靜態檢查對變更的 prompt 欄位一體適用
        check_prompt_fields(
            {f: after.get(f, "") for f in PROMPT_FIELDS if f in changed}
        )
        version = BotConfigVersion(
            tenant_id=bot.tenant_id,
            bot_id=bot.id.value,
            version_no=await self._version_repo.next_version_no(
                bot.id.value
            ),
            config_snapshot=after,
            snapshot_schema=SNAPSHOT_SCHEMA,
            changed_fields=changed,
            source=SOURCE_MANUAL,
            author_user_id=actor_user_id,  # Issue #60：PUT 路徑原本恆 None
        )
        version.mark_published(VERDICT_SKIPPED)
        await self._version_repo.save(version)
        await self._version_repo.set_current(bot.id.value, version.id)

    async def execute(self, command: UpdateBotCommand) -> Bot:
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", command.bot_id)
        # C9：跨租戶竄改 → 404（tenant_id 為 None 時代表 router 未帶入，維持舊行為）
        if command.tenant_id is not None:
            ensure_bot_tenant(bot, command.tenant_id, command.role)

        before_snapshot = take_snapshot(bot)
        before_view = self._audit_view(bot) if self._audit is not None else None

        # Capture old bindings before update (may contain encrypted env_values)
        old_bindings_map = {b.registry_id: b for b in bot.mcp_bindings}

        self._apply_updates(bot, command)

        # Handle mcp_bindings with encryption + masking
        if command.mcp_bindings is not _UNSET:
            bot.mcp_bindings = self._encrypt_bindings(
                command.mcp_bindings,  # type: ignore[arg-type]
                old_bindings_map,
            )

        # Issue #54 Phase C — gate_mode 啟用前置條件（application 層驗證先例）
        if command.gate_mode is not _UNSET and bot.gate_mode != "off":
            await self._ensure_dataset_bound(bot)

        await self._record_config_version(
            bot, before_snapshot, actor_user_id=command.actor_user_id
        )
        await self._bot_repo.save(bot)
        if self._audit is not None:
            await self._audit.record(
                entity_type="bot", entity_id=bot.id.value, action="update",
                before=before_view, after=self._audit_view(bot),
                actor_user_id=command.actor_user_id, tenant_id=bot.tenant_id,
            )
        if self._cache_service is not None:
            await self._cache_service.delete(f"bot:{command.bot_id}")
            await self._cache_service.delete(f"bot:sc:{bot.short_code.value}")

        return bot
