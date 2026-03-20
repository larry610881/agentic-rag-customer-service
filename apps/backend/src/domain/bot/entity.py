from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.bot.value_objects import BotId, BotShortCode


@dataclass(frozen=True)
class McpToolMeta:
    """MCP Tool 元資料（Value Object）"""

    name: str
    description: str = ""


@dataclass(frozen=True)
class McpServerConfig:
    """MCP Server 配置（Value Object）"""

    url: str
    name: str
    enabled_tools: list[str] = field(default_factory=list)
    tools: list[McpToolMeta] = field(default_factory=list)
    version: str = ""


@dataclass(frozen=True)
class BotMcpBinding:
    """Bot 與 MCP Registry Server 的綁定（Value Object）"""

    registry_id: str
    enabled_tools: list[str] = field(default_factory=list)
    env_values: dict[str, str] = field(default_factory=dict)


@dataclass
class BotLLMParams:
    temperature: float = 0.3
    max_tokens: int = 1024
    history_limit: int = 10
    frequency_penalty: float = 0.0
    reasoning_effort: str = "medium"  # low | medium | high
    rag_top_k: int = 5
    rag_score_threshold: float = 0.3


@dataclass
class Bot:
    id: BotId = field(default_factory=BotId)
    short_code: BotShortCode = field(default_factory=BotShortCode)
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    is_active: bool = True
    system_prompt: str = ""
    knowledge_base_ids: list[str] = field(default_factory=list)
    llm_params: BotLLMParams = field(default_factory=BotLLMParams)
    enabled_tools: list[str] = field(default_factory=lambda: ["rag_query"])
    llm_provider: str = ""
    llm_model: str = ""
    show_sources: bool = True
    agent_mode: str = "router"
    mcp_servers: list[McpServerConfig] = field(default_factory=list)
    mcp_bindings: list[BotMcpBinding] = field(default_factory=list)
    max_tool_calls: int = 5
    audit_mode: str = "minimal"  # "minimal" | "full"
    eval_provider: str = ""  # Eval LLM provider (independent from bot LLM)
    eval_model: str = ""  # Eval LLM model
    eval_depth: str = "L1"  # "off" | any combo of "L1", "L2", "L3" joined by "+"
    base_prompt: str = ""       # 空 = 用系統預設
    router_prompt: str = ""     # 空 = 用系統預設
    react_prompt: str = ""      # 空 = 用系統預設
    fab_icon_url: str = ""
    widget_enabled: bool = False
    widget_allowed_origins: list[str] = field(default_factory=list)
    widget_keep_history: bool = True
    widget_welcome_message: str = ""
    widget_placeholder_text: str = ""
    widget_greeting_messages: list[str] = field(default_factory=list)
    widget_greeting_animation: str = "fade"  # fade | slide | typewriter
    memory_enabled: bool = False
    memory_extraction_threshold: int = 3
    memory_extraction_prompt: str = ""
    busy_reply_message: str = "小編正在努力回覆中，請稍等一下喔～"
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
