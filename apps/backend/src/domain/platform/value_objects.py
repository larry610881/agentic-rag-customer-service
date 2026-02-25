from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


@dataclass(frozen=True)
class ProviderSettingId:
    value: str = field(default_factory=lambda: str(uuid4()))


class ProviderType(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"


class ProviderName(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    QWEN = "qwen"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    FAKE = "fake"


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    display_name: str
    is_default: bool = False
