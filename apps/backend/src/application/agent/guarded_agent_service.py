"""GuardedAgentService — 把 prompt-injection guard 掛在 AgentService 共用咽喉點。

所有 channel（web / LINE / 未來 WhatsApp…）最終都會呼叫
`AgentService.process_message()`。把 guard 包在這個共用收斂點，讓防護「預設
生效」，而不是每個 entry-point use case 各自 opt-in —— LINE 就是因為
`HandleWebhookUseCase` 沒有 opt-in 而完全裸奔。

分工：
- `process_message`（非串流，LINE 走這條）→ 在此做完整 input + output guard。
- `process_message_stream` → 目前唯一呼叫者是 web `SendMessageUseCase`，它自身
  已對串流做完整 guard，且與 conversation/trace 持久化、SSE 事件契約深綁。為避免
  雙重 guard / 雙重 SSE 事件，此處串流直接委派 inner。待未來出現「會串流且未自帶
  guard」的 channel 時再擴充。
- 其他方法（例如 `.start()`）透過 `__getattr__` 代理到 inner。

注意：本 decorator 只負責「攔截」（enforcement）。channel-specific 呈現
（Studio SSE 事件、LINE 回覆文字、trace 紅節點持久化）仍由各 entry-point 依
`AgentResponse.guard_blocked` 自行處理。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message


class GuardedAgentService(AgentService):
    """Decorator：在共用咽喉點強制套用 prompt injection guard。"""

    def __init__(
        self,
        inner: AgentService,
        prompt_guard: Any | None = None,
    ) -> None:
        self._inner = inner
        self._prompt_guard = prompt_guard

    def __getattr__(self, name: str) -> Any:
        # 只在正常屬性查找失敗時觸發；_inner 已於 __init__ 設好，代理其餘方法/屬性。
        return getattr(self._inner, name)

    async def process_message(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        kb_ids: list[str] | None = None,
        system_prompt: str | None = None,
        llm_params: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        bot_id: str = "",
    ) -> AgentResponse:
        # ── Input guard（LLM 前第一道；命中直接短路，不進 agent）──
        if self._prompt_guard is not None:
            guard_result = await self._prompt_guard.check_input(
                user_message,
                tenant_id=tenant_id,
                bot_id=bot_id or None,
            )
            if not guard_result.passed:
                return AgentResponse(
                    answer=guard_result.blocked_response,
                    guard_blocked="input",
                    guard_rule_matched=guard_result.rule_matched,
                )

        response = await self._inner.process_message(
            tenant_id,
            kb_id,
            user_message,
            history,
            kb_ids=kb_ids,
            system_prompt=system_prompt,
            llm_params=llm_params,
            metadata=metadata,
            history_context=history_context,
            router_context=router_context,
            enabled_tools=enabled_tools,
            rag_top_k=rag_top_k,
            rag_score_threshold=rag_score_threshold,
            tool_rag_params=tool_rag_params,
            customer_service_url=customer_service_url,
            mcp_servers=mcp_servers,
            max_tool_calls=max_tool_calls,
            bot_id=bot_id,
        )

        # ── Output guard（命中則以 blocked_response 取代原文）──
        if self._prompt_guard is not None and response.answer:
            output_guard = await self._prompt_guard.check_output(
                response.answer,
                tenant_id=tenant_id,
                bot_id=bot_id or None,
                user_message=user_message,
            )
            if not output_guard.passed:
                response.answer = output_guard.blocked_response
                response.guard_blocked = "output"
                response.guard_rule_matched = output_guard.rule_matched

        return response

    async def process_message_stream(  # type: ignore[override]
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        kb_ids: list[str] | None = None,
        system_prompt: str | None = None,
        llm_params: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        bot_id: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        # 見 module docstring：串流唯一呼叫者（web）已自帶完整 guard，委派即可。
        # ABC 把本方法標為 `async def -> AsyncIterator`（coroutine 回傳 iterator），
        # 但實作皆為 async generator；此 quirk 全庫既有（見 react_agent_service）。
        async for event in self._inner.process_message_stream(  # type: ignore[attr-defined]
            tenant_id,
            kb_id,
            user_message,
            history,
            kb_ids=kb_ids,
            system_prompt=system_prompt,
            llm_params=llm_params,
            metadata=metadata,
            history_context=history_context,
            router_context=router_context,
            enabled_tools=enabled_tools,
            rag_top_k=rag_top_k,
            rag_score_threshold=rag_score_threshold,
            tool_rag_params=tool_rag_params,
            customer_service_url=customer_service_url,
            mcp_servers=mcp_servers,
            max_tool_calls=max_tool_calls,
            bot_id=bot_id,
        ):
            yield event
