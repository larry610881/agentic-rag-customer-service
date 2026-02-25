from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.platform.value_objects import (
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
