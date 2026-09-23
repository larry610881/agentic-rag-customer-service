"""Repository 單元測試用的 spy session（Issue #101）。

目的是驗「查詢條件」而不是驗資料庫：記下每個被 execute 的 SQLAlchemy 語句，
讓測試斷言 WHERE 子句含租戶過濾（tenant_id）等條件。回傳值預設為「查無資料」，
需要讓程式走到資料分支時用 queue_result() 逐次指定。

不要為了衝覆蓋率去 mock 每個方法的回傳值——測的是條件存在與否。
"""

from __future__ import annotations

from collections import deque
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.dialects import postgresql


class FakeResult:
    """模擬 SQLAlchemy Result 的常用讀法；rows 為要回傳的資料列（ORM 物件或 tuple）。"""

    def __init__(self, rows: list[Any] | None = None, rowcount: int = 0) -> None:
        self._rows = list(rows or [])
        self.rowcount = rowcount

    # Result
    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def one_or_none(self) -> Any:
        return self.first()

    def scalar_one_or_none(self) -> Any:
        return self.first()

    def scalar_one(self) -> Any:
        return self._rows[0] if self._rows else 0

    def scalar(self) -> Any:
        return self.first()

    def fetchall(self) -> list[Any]:
        return self.all()

    def tuples(self) -> FakeResult:
        return self

    def unique(self) -> FakeResult:
        return self

    def scalars(self) -> FakeResult:
        return self

    def mappings(self) -> FakeResult:
        return self

    def __iter__(self):
        return iter(self._rows)


class SpySession:
    """AsyncSession 替身：記錄語句，不連資料庫。"""

    def __init__(self) -> None:
        self.statements: list[Any] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.merged: list[Any] = []
        self.commits = 0
        self._queued: deque[FakeResult] = deque()
        self.get_result: Any = None

    # ---- 測試控制 ----
    def queue_result(self, rows: list[Any] | None = None, rowcount: int = 0) -> None:
        """指定下一次 execute 的回傳（先進先出）；未指定則回傳空結果。"""
        self._queued.append(FakeResult(rows, rowcount))

    def sql(self, index: int = -1) -> str:
        """第 index 次 execute 的語句，以 PostgreSQL 方言編譯成含字面值的 SQL。"""
        return compile_sql(self.statements[index])

    def all_sql(self) -> list[str]:
        return [compile_sql(s) for s in self.statements]

    # ---- AsyncSession 介面 ----
    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:
        self.statements.append(stmt)
        return self._queued.popleft() if self._queued else FakeResult()

    async def scalar(self, stmt: Any, *args: Any, **kwargs: Any) -> Any:
        return (await self.execute(stmt)).scalar()

    async def scalars(self, stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:
        return await self.execute(stmt)

    async def get(self, model: Any, pk: Any, *args: Any, **kwargs: Any) -> Any:
        return self.get_result

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def merge(self, obj: Any, *args: Any, **kwargs: Any) -> Any:
        self.merged.append(obj)
        return obj

    async def flush(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def refresh(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None

    async def close(self) -> None:
        return None

    @asynccontextmanager
    async def begin_nested(self):
        yield

    @asynccontextmanager
    async def begin(self):
        yield


def compile_sql(stmt: Any) -> str:
    """把語句編譯成 PostgreSQL SQL 字串（字面值內嵌，便於斷言條件）。"""
    try:
        return str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
    except Exception:
        # 部分型別（JSONB、陣列）無法內嵌字面值，退回參數化 SQL（條件欄位名仍在）
        return str(stmt.compile(dialect=postgresql.dialect()))
