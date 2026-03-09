from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.bot.value_objects import BotId, BotShortCode


@dataclass(frozen=True)
class McpServerConfig:
    """MCP Server 配置（Value Object）"""

    url: str
    name: str
    enabled_tools: list[str] = field(default_factory=list)


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
    max_tool_calls: int = 5
    audit_mode: str = "minimal"  # "minimal" | "full"
    eval_provider: str = ""  # Eval LLM provider (independent from bot LLM)
    eval_model: str = ""  # Eval LLM model
    eval_depth: str = "L1"  # "L1" | "L1+L2" | "L1+L2+L3"
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
