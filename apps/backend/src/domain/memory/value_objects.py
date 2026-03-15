from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class VisitorProfileId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class VisitorIdentityId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class MemoryFactId:
    value: str = field(default_factory=lambda: str(uuid4()))


# Memory type constants
MEMORY_TYPE_SHORT_TERM = "short_term"
MEMORY_TYPE_LONG_TERM = "long_term"
MEMORY_TYPE_EPISODIC = "episodic"

# Memory category constants
CATEGORY_PERSONAL_INFO = "personal_info"
CATEGORY_PREFERENCE = "preference"
CATEGORY_PAST_ISSUE = "past_issue"
CATEGORY_PURCHASE = "purchase"
CATEGORY_SENTIMENT = "sentiment"
CATEGORY_CUSTOM = "custom"
