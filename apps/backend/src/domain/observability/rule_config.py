"""診斷規則設定 — Domain Entity + Repository Interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DiagnosticRulesConfig:
    """全域診斷規則設定（singleton, id='default'）"""

    id: str = "default"
    single_rules: list[dict] = field(default_factory=list)
    combo_rules: list[dict] = field(default_factory=list)
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DiagnosticRulesConfigRepository(ABC):
    @abstractmethod
    async def get(self) -> DiagnosticRulesConfig | None: ...

    @abstractmethod
    async def save(self, config: DiagnosticRulesConfig) -> None: ...

    @abstractmethod
    async def delete(self) -> None: ...
