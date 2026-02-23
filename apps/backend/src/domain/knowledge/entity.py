from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.knowledge.value_objects import KnowledgeBaseId


@dataclass
class KnowledgeBase:
    id: KnowledgeBaseId = field(default_factory=KnowledgeBaseId)
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
