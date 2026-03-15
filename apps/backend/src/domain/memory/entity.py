from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.memory.value_objects import (
    MemoryFactId,
    VisitorIdentityId,
    VisitorProfileId,
)


@dataclass
class VisitorIdentity:
    """Identity binding: maps an external source identity to a VisitorProfile."""

    id: VisitorIdentityId = field(default_factory=VisitorIdentityId)
    profile_id: str = ""
    tenant_id: str = ""
    source: str = ""  # "widget" | "line" | "jwt"
    external_id: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class VisitorProfile:
    """Aggregate Root: represents a unique visitor across conversations."""

    id: VisitorProfileId = field(default_factory=VisitorProfileId)
    tenant_id: str = ""
    display_name: str | None = None
    identities: list[VisitorIdentity] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_identity(
        self, source: str, external_id: str
    ) -> VisitorIdentity:
        identity = VisitorIdentity(
            id=VisitorIdentityId(),
            profile_id=self.id.value,
            tenant_id=self.tenant_id,
            source=source,
            external_id=external_id,
        )
        self.identities.append(identity)
        return identity


@dataclass
class MemoryFact:
    """Independent Aggregate: a single remembered fact about a visitor."""

    id: MemoryFactId = field(default_factory=MemoryFactId)
    profile_id: str = ""
    tenant_id: str = ""
    memory_type: str = "long_term"  # "short_term" | "long_term" | "episodic"
    # "personal_info"|"preference"|"past_issue"|"purchase"|"sentiment"|"custom"
    category: str = "custom"
    key: str = ""
    value: str = ""
    source_conversation_id: str | None = None
    confidence: float = 1.0
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
