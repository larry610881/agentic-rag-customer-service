from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncIterator[None]:
    """Wrap write operations in an explicit transaction with commit.

    Uses SAVEPOINT (begin_nested) so that:
    - If autobegin already started a transaction (e.g. from a prior read),
      the write still gets committed via the outer commit().
    - Nested atomic() calls create nested SAVEPOINTs (safe).
    - On exception, the SAVEPOINT is rolled back and commit() is skipped.
    """
    async with session.begin_nested():
        yield
    await session.commit()
