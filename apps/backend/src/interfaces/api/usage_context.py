"""Usage 分類標記的 FastAPI dependency（Issue #54 Phase B）

純轉接：讀 header + JWT role，委派 application 層的 resolve_usage_context。
"""

from __future__ import annotations

from fastapi import Depends, Request

from src.application.usage.usage_context import (
    EVAL_RUN_ID_HEADER,
    USAGE_CATEGORY_HEADER,
    UsageContext,
    resolve_usage_context,
)
from src.interfaces.api.deps import CurrentTenant, authenticate

__all__ = ["UsageContext", "get_usage_context"]


async def get_usage_context(
    request: Request,
    tenant: CurrentTenant = Depends(authenticate),
) -> UsageContext:
    return resolve_usage_context(
        category=request.headers.get(USAGE_CATEGORY_HEADER),
        run_id=request.headers.get(EVAL_RUN_ID_HEADER),
        role=tenant.role,
    )
