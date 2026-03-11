"""ContextVar bridge for captured error detail."""

from contextvars import ContextVar

_captured_error: ContextVar[str | None] = ContextVar("captured_error", default=None)


def set_captured_error(detail: str | None) -> None:
    _captured_error.set(detail)


def get_captured_error() -> str | None:
    return _captured_error.get()


def reset_captured_error() -> None:
    _captured_error.set(None)
