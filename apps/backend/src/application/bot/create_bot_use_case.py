"""建立機器人用例"""

from dataclasses import dataclass, field

from src.domain.bot.entity import (
    Bot,
    BotLLMParams,
    BotMcpBinding,
    McpServerConfig,
    McpToolMeta,
)
from src.domain.bot.repository import BotRepository
from src.domain.platform.services import EncryptionService


@dataclass(frozen=True)
class CreateBotCommand:
    tenant_id: str
    name: str
    description: str = ""
    knowledge_base_ids: list[str] = field(default_factory=list)
    system_prompt: str = ""
    is_active: bool = True
    temperature: float = 0.3
    max_tokens: int = 1024
    history_limit: int = 10
    frequency_penalty: float = 0.0
    reasoning_effort: str = "medium"
    rag_top_k: int = 5
    rag_score_threshold: float = 0.3
    enabled_tools: list[str] = field(default_factory=lambda: ["rag_query"])
    llm_provider: str = ""
    llm_model: str = ""
    show_sources: bool = True
    agent_mode: str = "router"
    audit_mode: str = "minimal"
    eval_provider: str = ""
    eval_model: str = ""
    eval_depth: str = "L1"
    mcp_servers: list[dict] = field(default_factory=list)
    mcp_bindings: list[dict] = field(default_factory=list)
    max_tool_calls: int = 5
    base_prompt: str = ""
    router_prompt: str = ""
    react_prompt: str = ""
    widget_enabled: bool = False
    widget_allowed_origins: list[str] = field(default_factory=list)
    widget_keep_history: bool = True
    avatar_type: str = "none"
    avatar_model_url: str = ""
    widget_welcome_message: str = ""
    widget_placeholder_text: str = ""
    widget_greeting_messages: list[str] = field(default_factory=list)
    widget_greeting_animation: str = "fade"
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None


class CreateBotUseCase:
    def __init__(
        self,
        bot_repository: BotRepository,
        encryption_service: EncryptionService | None = None,
    ) -> None:
        self._bot_repo = bot_repository
        self._encryption = encryption_service

    async def execute(self, command: CreateBotCommand) -> Bot:
        # Build MCP bindings with encrypted env_values
        mcp_bindings = []
        for b in command.mcp_bindings:
            raw_env = b.get("env_values", {})
            encrypted_env = {
                k: self._encryption.encrypt(v) if v and self._encryption else v
                for k, v in raw_env.items()
            }
            mcp_bindings.append(
                BotMcpBinding(
                    registry_id=b.get("registry_id", ""),
                    enabled_tools=b.get("enabled_tools", []),
                    env_values=encrypted_env,
                )
            )

        bot = Bot(
            tenant_id=command.tenant_id,
            name=command.name,
            description=command.description,
            is_active=command.is_active,
            system_prompt=command.system_prompt,
            knowledge_base_ids=list(command.knowledge_base_ids),
            llm_params=BotLLMParams(
                temperature=command.temperature,
                max_tokens=command.max_tokens,
                history_limit=command.history_limit,
                frequency_penalty=command.frequency_penalty,
                reasoning_effort=command.reasoning_effort,
                rag_top_k=command.rag_top_k,
                rag_score_threshold=command.rag_score_threshold,
            ),
            enabled_tools=list(command.enabled_tools),
            llm_provider=command.llm_provider,
            llm_model=command.llm_model,
            show_sources=command.show_sources,
            agent_mode=command.agent_mode,
            audit_mode=command.audit_mode,
            eval_provider=command.eval_provider,
            eval_model=command.eval_model,
            eval_depth=command.eval_depth,
            mcp_servers=[
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
                for s in command.mcp_servers
            ],
            mcp_bindings=mcp_bindings,
            max_tool_calls=command.max_tool_calls,
            widget_enabled=command.widget_enabled,
            widget_allowed_origins=list(command.widget_allowed_origins),
            widget_keep_history=command.widget_keep_history,
            avatar_type=command.avatar_type,
            avatar_model_url=command.avatar_model_url,
            widget_welcome_message=command.widget_welcome_message,
            widget_placeholder_text=command.widget_placeholder_text,
            widget_greeting_messages=list(command.widget_greeting_messages),
            widget_greeting_animation=command.widget_greeting_animation,
            base_prompt=command.base_prompt,
            router_prompt=command.router_prompt,
            react_prompt=command.react_prompt,
            line_channel_secret=command.line_channel_secret,
            line_channel_access_token=command.line_channel_access_token,
        )
        await self._bot_repo.save(bot)
        return bot
