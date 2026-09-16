"""長期記憶的通路共用服務（channel-parity 債務第 6 項）。

web / widget 原本在 SendMessageUseCase 內做「解析身分 → 載入記憶 → 對話達門檻排程
萃取」，
LINE 完全沒接（memory_enabled 對 LINE 靜默無效）。抽成這一份，三通路呼叫。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

EnqueueFn = Callable[..., Awaitable[Any]]


class ConversationMemoryService:
    def __init__(
        self,
        resolve_identity: Any | None = None,
        load_memory: Any | None = None,
        extract_memory: Any | None = None,
        enqueue: EnqueueFn | None = None,
    ) -> None:
        self._resolve_identity = resolve_identity
        self._load_memory = load_memory
        self._extract_memory = extract_memory
        self._enqueue = enqueue

    @property
    def available(self) -> bool:
        return self._resolve_identity is not None

    async def load_prompt(
        self,
        *,
        tenant_id: str,
        source: str | None,
        external_id: str | None,
        memory_enabled: bool,
    ) -> str:
        """回傳可接在 history_context 前面的記憶提示；關閉 / 缺身分 / 失敗 → 空字串。"""
        if not memory_enabled or not external_id or not source:
            return ""
        if self._resolve_identity is None or self._load_memory is None:
            return ""
        try:
            from src.application.memory.load_memory_use_case import LoadMemoryCommand
            from src.application.memory.resolve_identity_use_case import (
                ResolveIdentityCommand,
            )

            profile_id = await self._resolve_identity.execute(
                ResolveIdentityCommand(
                    tenant_id=tenant_id, source=source, external_id=external_id
                )
            )
            memory_ctx = await self._load_memory.execute(
                LoadMemoryCommand(profile_id=profile_id)
            )
            if memory_ctx.has_memory:
                return str(memory_ctx.formatted_prompt)
        except Exception:
            logger.warning("memory.load_failed", exc_info=True)
        return ""

    @staticmethod
    def should_extract(
        memory_enabled: bool, threshold: int, message_count: int
    ) -> bool:
        if not memory_enabled:
            return False
        return message_count >= max(int(threshold or 3), 1) * 2

    async def schedule_extraction(
        self,
        *,
        tenant_id: str,
        source: str | None,
        external_id: str | None,
        conversation: Any,
        memory_enabled: bool,
        threshold: int,
        extraction_prompt: str,
        bot_id: str,
    ) -> bool:
        """對話達門檻時排程背景萃取（只送最後一組 user+assistant）。

        回傳是否已排程。
        """
        if not external_id or not source:
            return False
        if self._resolve_identity is None or self._extract_memory is None:
            return False
        n_messages = len(conversation.messages)
        if not self.should_extract(memory_enabled, threshold, n_messages):
            return False
        try:
            from src.application.memory.resolve_identity_use_case import (
                ResolveIdentityCommand,
            )

            profile_id = await self._resolve_identity.execute(
                ResolveIdentityCommand(
                    tenant_id=tenant_id, source=source, external_id=external_id
                )
            )
            recent_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in conversation.messages[-2:]
            ]
            enqueue = self._enqueue
            if enqueue is None:
                from src.infrastructure.queue.arq_pool import enqueue as _enqueue

                enqueue = _enqueue
            await enqueue(
                "extract_memory",
                profile_id,
                tenant_id,
                conversation.id.value,
                recent_messages,
                extraction_prompt,
                bot_id,  # Issue #73：memory_extraction 用量歸屬
            )
            return True
        except Exception:
            logger.warning("memory.extraction_dispatch_failed", exc_info=True)
            return False
