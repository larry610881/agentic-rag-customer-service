"""更新機器人用例"""

from dataclasses import dataclass, replace

from src.domain.bot.entity import (
    Bot,
    BotMcpBinding,
    IntentRoute,
    McpServerConfig,
    McpToolMeta,
)
from src.domain.bot.repository import BotRepository
from src.domain.platform.services import EncryptionService
from src.domain.shared.cache_service import CacheService
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError

_UNSET = object()

# 前端送回此遮罩值表示「保留原加密值」
_MASKED_VALUE = "***"


@dataclass(frozen=True)
class UpdateBotCommand:
    bot_id: str
    name: object = _UNSET
    description: object = _UNSET
    is_active: object = _UNSET
    knowledge_base_ids: object = _UNSET
    system_prompt: object = _UNSET
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
    audit_mode: object = _UNSET
    eval_provider: object = _UNSET
    eval_model: object = _UNSET
    eval_depth: object = _UNSET
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
    ) -> None:
        self._bot_repo = bot_repository
        self._cache_service = cache_service
        self._encryption = encryption_service

    @staticmethod
    def _apply_updates(bot: Bot, command: UpdateBotCommand) -> None:
        """Apply non-_UNSET fields from command to bot entity."""
        _DIRECT_FIELDS = (
            "name", "description", "is_active",
            "system_prompt",
            "llm_provider", "llm_model", "show_sources",
            "audit_mode",
            "eval_provider", "eval_model", "eval_depth",
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
            if val is not _UNSET:
                setattr(bot, field, val)

        if command.knowledge_base_ids is not _UNSET:
            bot.knowledge_base_ids = list(command.knowledge_base_ids)  # type: ignore[arg-type]
        if command.enabled_tools is not _UNSET:
            bot.enabled_tools = list(command.enabled_tools)  # type: ignore[arg-type]
        if command.widget_allowed_origins is not _UNSET:
            bot.widget_allowed_origins = list(command.widget_allowed_origins)  # type: ignore[arg-type]
        if command.widget_greeting_messages is not _UNSET:
            bot.widget_greeting_messages = list(command.widget_greeting_messages)  # type: ignore[arg-type]
        if command.rerank_enabled is not _UNSET:
            bot.rerank_enabled = command.rerank_enabled  # type: ignore[assignment]
        if command.rerank_model is not _UNSET:
            bot.rerank_model = command.rerank_model  # type: ignore[assignment]
        if command.rerank_top_n is not _UNSET:
            bot.rerank_top_n = command.rerank_top_n  # type: ignore[assignment]
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

    async def execute(self, command: UpdateBotCommand) -> Bot:
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", command.bot_id)

        # Capture old bindings before update (may contain encrypted env_values)
        old_bindings_map = {b.registry_id: b for b in bot.mcp_bindings}

        self._apply_updates(bot, command)

        # Handle mcp_bindings with encryption + masking
        if command.mcp_bindings is not _UNSET:
            bot.mcp_bindings = self._encrypt_bindings(
                command.mcp_bindings,  # type: ignore[arg-type]
                old_bindings_map,
            )

        await self._bot_repo.save(bot)
        if self._cache_service is not None:
            await self._cache_service.delete(f"bot:{command.bot_id}")
        return bot
