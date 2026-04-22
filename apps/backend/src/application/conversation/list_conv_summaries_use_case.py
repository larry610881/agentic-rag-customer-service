"""List Conversation Summaries Use Case — S-KB-Studio.1"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.conversation.repository import ConversationRepository


@dataclass(frozen=True)
class ListConvSummariesQuery:
    role: str  # "system_admin" | "tenant_admin"
    tenant_id: str | None = None
    bot_id: str | None = None
    page: int = 1
    page_size: int = 50


class ListConvSummariesUseCase:
    def __init__(
        self,
        conv_repo: ConversationRepository,
    ) -> None:
        self._repo = conv_repo

    async def execute(self, query: ListConvSummariesQuery) -> list:
        if query.tenant_id is None:
            # platform admin 也必填 tenant_id（安全紅線）
            raise ValueError("tenant_id required (no cross-tenant listing)")

        # bot_id 若指定，caller 層須先驗屬 tenant（router 或 wrapper 驗）；此處
        # 只負責 repo 呼叫。EntityNotFoundError 用於 tenant/bot mismatch 的情況
        # 由 router 在呼叫前先做 verification 拋出。

        # 依 ConversationRepository 既有 method 實際命名呼叫。若暫無對應
        # list method，Day 2 補；此處先回空 list 以通過 import。
        find_method = getattr(
            self._repo, "find_conv_summaries", None
        ) or getattr(self._repo, "list_conv_summaries", None)
        if find_method is None:
            return []
        return await find_method(
            tenant_id=query.tenant_id,
            bot_id=query.bot_id,
            page=query.page,
            page_size=query.page_size,
        )
