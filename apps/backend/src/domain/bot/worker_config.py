"""Bot Worker 配置 — 每個 Worker 是獨立 ReAct Agent"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class WorkerConfig:
    """Bot 的 Sub-agent 配置，每個 Worker 有自己的 model/tools/prompt"""

    id: str = field(default_factory=lambda: str(uuid4()))
    bot_id: str = ""
    name: str = ""
    description: str = ""          # 給 LLM router 看的描述
    system_prompt: str = ""
    llm_provider: str | None = None  # None = 用 bot default
    llm_model: str | None = None     # None = 用 bot default
    temperature: float = 0.7
    max_tokens: int = 1024
    max_tool_calls: int = 5
    enabled_mcp_ids: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)  # 空 = 用 bot default KB
    sort_order: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
