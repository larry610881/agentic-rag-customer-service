"""Infrastructure implementation of ErrorReporter using ContextVar."""

from src.domain.shared.error_reporter import ErrorContext, ErrorReporter
from src.infrastructure.logging.error_context import set_captured_error


class DBErrorReporter(ErrorReporter):
    """Captures error detail into a ContextVar for the middleware to read."""

    async def capture(self, exc: Exception, ctx: ErrorContext) -> None:
        detail = f"{type(exc).__name__}: {exc}"
        set_captured_error(detail)
