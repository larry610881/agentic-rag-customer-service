"""共用分頁 API Schema"""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PaginationQuery:
    """FastAPI Depends() 用的分頁參數。

    page_size 上限 500：admin 後台會用 page_size=200 列出所有 bots/KBs，
    一般租戶頁面則自然不會超過 100。500 是務實的上限避免攻擊面（前端不會
    一次抓 500，但 admin debug 偶爾會）。
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
