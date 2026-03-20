"""併發控制抽象介面"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ConversationLock(ABC):
    """Conversation-level lock to prevent concurrent agent runs.

    Usage:
        async with lock.acquire("conv_lock:xxx", timeout=120) as acquired:
            if not acquired:
                # Another run is in progress
                return busy_reply_message
            # Proceed with agent run
    """

    @abstractmethod
    @asynccontextmanager
    async def acquire(
        self, lock_key: str, *, timeout: int = 120
    ) -> AsyncIterator[bool]:
        """Try to acquire a lock.

        Yields True if lock acquired, False if already held.
        Lock is released on exit.
        """
        yield False  # pragma: no cover
