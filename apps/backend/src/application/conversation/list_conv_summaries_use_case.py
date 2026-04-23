"""List Conversation Summaries Use Case — S-KB-Studio.1

S-KB-Followup.1 (2026-04-23) 加上 bot_id ownership check 堵 IDOR。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.bot.repository import BotRepository
from src.domain.conversation.repository import ConversationRepository
from src.domain.shared.exceptions import EntityNotFoundError


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
        bot_repo: BotRepository,
    ) -> None:
        self._repo = conv_repo
        self._bot_repo = bot_repo

    async def execute(self, query: ListConvSummariesQuery) -> list:
        if query.tenant_id is None:
            # platform admin 也必填 tenant_id（安全紅線）
            raise ValueError("tenant_id required (no cross-tenant listing)")

        # IDOR 防護：bot_id 必須屬於該 tenant，否則 404 防枚舉
        if query.bot_id:
            owned = await self._bot_repo.exists_for_tenant(
                query.bot_id, query.tenant_id
            )
            if not owned:
                raise EntityNotFoundError("bot", query.bot_id)

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
