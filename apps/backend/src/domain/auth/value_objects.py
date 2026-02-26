from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


@dataclass(frozen=True)
class UserId:
    value: str = field(default_factory=lambda: str(uuid4()))


class Role(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    TENANT_ADMIN = "tenant_admin"
    USER = "user"


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not self.value or "@" not in self.value:
            raise ValueError(f"Invalid email: {self.value}")
