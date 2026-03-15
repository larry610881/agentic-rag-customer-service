"""Notification Channel — Domain Entity + Repository + Strategy Interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class NotificationChannel:
    id: str
    channel_type: str  # 'email' | 'slack' | 'teams'
    name: str
    enabled: bool = False
    config_encrypted: str = "{}"
    throttle_minutes: int = 15
    min_severity: str = "all"  # 'all' | '5xx_only'
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationChannelRepository(ABC):
    @abstractmethod
    async def save(
        self, channel: NotificationChannel
    ) -> NotificationChannel: ...

    @abstractmethod
    async def get_by_id(
        self, channel_id: str
    ) -> NotificationChannel | None: ...

    @abstractmethod
    async def list_all(self) -> list[NotificationChannel]: ...

    @abstractmethod
    async def list_enabled(self) -> list[NotificationChannel]: ...

    @abstractmethod
    async def delete(self, channel_id: str) -> bool: ...


class NotificationSender(ABC):
    """Strategy interface — one implementation per channel type."""

    @abstractmethod
    async def send(
        self, channel: NotificationChannel, subject: str, body: str
    ) -> None: ...

    @abstractmethod
    def channel_type(self) -> str: ...
