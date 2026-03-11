"""Domain interface for error reporting."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorContext:
    request_id: str
    tenant_id: str | None
    method: str
    path: str
    status_code: int


class ErrorReporter(ABC):
    @abstractmethod
    async def capture(self, exc: Exception, ctx: ErrorContext) -> None: ...
