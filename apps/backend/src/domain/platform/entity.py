from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.platform.value_objects import (
    McpRegistryId,
    McpRegistryToolMeta,
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)


@dataclass
class ProviderSetting:
    id: ProviderSettingId = field(default_factory=ProviderSettingId)
    provider_type: ProviderType = ProviderType.LLM
    provider_name: ProviderName = ProviderName.OPENAI
    display_name: str = ""
    is_enabled: bool = True
    api_key_encrypted: str = ""
    base_url: str = ""
    models: list[ModelConfig] = field(default_factory=list)
    extra_config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def disable(self) -> None:
        self.is_enabled = False
        self.updated_at = datetime.now(timezone.utc)

    def enable(self) -> None:
        self.is_enabled = True
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class SystemPromptConfig:
    """系統層級 Prompt 預設值（singleton, id='default'）"""

    id: str = "default"
    base_prompt: str = ""
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class McpServerRegistration:
    """MCP Server 全域註冊表（Platform 層級）"""

    id: McpRegistryId = field(default_factory=McpRegistryId)
    name: str = ""
    description: str = ""
    transport: str = "http"          # "http" | "stdio"
    url: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    required_env: list[str] = field(default_factory=list)
    available_tools: list[McpRegistryToolMeta] = field(default_factory=list)
    version: str = ""
    scope: str = "global"
    tenant_ids: list[str] = field(default_factory=list)
    is_enabled: bool = True
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
