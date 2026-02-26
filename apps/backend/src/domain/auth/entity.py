from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.auth.value_objects import Email, Role, UserId
from src.domain.shared.exceptions import DomainException


class TenantRequiredError(DomainException):
    def __init__(self, role: str) -> None:
        super().__init__(
            f"Role '{role}' requires a tenant_id"
        )


class TenantForbiddenError(DomainException):
    def __init__(self) -> None:
        super().__init__(
            "system_admin must not have a tenant_id"
        )


@dataclass
class User:
    id: UserId = field(default_factory=UserId)
    tenant_id: str | None = None
    email: Email = field(default_factory=lambda: Email("placeholder@example.com"))
    hashed_password: str = ""
    role: Role = Role.USER
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        self._validate_tenant_role()

    def _validate_tenant_role(self) -> None:
        if self.role == Role.SYSTEM_ADMIN and self.tenant_id is not None:
            raise TenantForbiddenError()
        if self.role in (Role.TENANT_ADMIN, Role.USER) and not self.tenant_id:
            raise TenantRequiredError(self.role.value)
