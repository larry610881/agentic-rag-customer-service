"""共用分頁領域物件"""

from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PaginationParams:
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True)
class PaginatedResult(Generic[T]):
    items: list
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return ceil(self.total / self.page_size) if self.total > 0 else 0
