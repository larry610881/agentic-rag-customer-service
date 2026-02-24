from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class BotId:
    value: str = field(default_factory=lambda: str(uuid4()))
