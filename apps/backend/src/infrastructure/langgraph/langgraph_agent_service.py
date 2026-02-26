"""LangGraphAgentService — 使用 LangGraph StateGraph 處理訊息"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import structlog

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import Source, TokenUsage
from src.infrastructure.langgraph.agent_graph import (
    RESPOND_SYSTEM_PROMPT,
    _extract_llm_kwargs,
    build_agent_graph,
)
from src.infrastructure.langgraph.tools import RAGQueryTool

logger = structlog.get_logger(__name__)


class LangGraphAgentService(AgentService):
    def __init__(
        self,
        llm_service: LLMService,
        rag_tool: RAGQueryTool,
    ) -> None:
        self._llm_service = llm_service
        # Full graph (routing + tool + respond)
        graph = build_agent_graph(llm_service, rag_tool)
        self._compiled = graph.compile()
        # Routing-only graph (no respond) — for streaming
        routing_graph = build_agent_graph(
            llm_service, rag_tool, include_respond=False,
        )
        self._compiled_routing = routing_graph.compile()

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
    ) -> AgentResponse:
        initial_state = {
            "messages": [],
            "user_message": user_message,
            "tenant_id": tenant_id,
            "kb_id": kb_id,
            "kb_ids": kb_ids or [],
            "system_prompt": system_prompt or "",
            "llm_params": llm_params or {},
            "history_context": history_context,
            "router_context": router_context,
            "current_tool": "",
            "tool_reasoning": "",
            "tool_result": {},
            "final_answer": "",
            "accumulated_usage": {},
            "enabled_tools": enabled_tools or [],
            "rag_top_k": rag_top_k,
            "rag_score_threshold": rag_score_threshold,
        }

        result = await self._compiled.ainvoke(initial_state)

        tool_name = result.get("current_tool", "")
        tool_reasoning = result.get("tool_reasoning", "")
        answer = result.get("final_answer", "")

        # Extract sources from RAG tool results
        sources: list[Source] = []
        tool_result = result.get("tool_result", {})
        if tool_name == "rag_query" and isinstance(tool_result, dict):
            raw_sources = tool_result.get("sources", [])
            sources = [
                Source(
                    document_name=s.get("document_name", ""),
                    content_snippet=s.get("content_snippet", ""),
                    score=s.get("score", 0.0),
                    chunk_id=s.get("chunk_id", ""),
                )
                for s in raw_sources
            ]

        # Convert accumulated_usage dict to TokenUsage
        acc = result.get("accumulated_usage", {})
        usage = (
            TokenUsage(
                model=acc.get("model", "unknown"),
                input_tokens=acc.get("input_tokens", 0),
                output_tokens=acc.get("output_tokens", 0),
                total_tokens=acc.get("total_tokens", 0),
                estimated_cost=acc.get("estimated_cost", 0.0),
            )
            if acc
            else None
        )

        return AgentResponse(
            answer=answer,
            tool_calls=[
                {"tool_name": tool_name, "reasoning": tool_reasoning},
            ],
            sources=sources,
            conversation_id=str(uuid4()),
            usage=usage,
        )

    @staticmethod
    def _build_respond_context(
        history_context: str,
        tool_result: dict[str, Any],
    ) -> str:
        """Build context string from history and tool result."""
        parts: list[str] = []
        if history_context:
            parts.append(f"[對話歷史]\n{history_context}")
        if tool_result:
            tool_json = json.dumps(
                tool_result, ensure_ascii=False, default=str
            )
            parts.append(f"[工具結果]\n{tool_json}")
        return "\n\n".join(parts)

    async def _stream_direct(
        self,
        user_message: str,
        system_prompt: str | None,
        llm_params: dict[str, Any] | None,
        history_context: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """No tools enabled — skip routing, stream LLM directly."""
        yield {
            "type": "tool_calls",
            "tool_calls": [
                {"tool_name": "direct", "reasoning": "無啟用工具"}
            ],
        }
        custom_prompt = system_prompt or ""
        sys_prompt = (
            custom_prompt
            if custom_prompt.strip()
            else RESPOND_SYSTEM_PROMPT
        )
        llm_kw: dict[str, Any] = {}
        params = llm_params or {}
        for k in ("temperature", "max_tokens", "frequency_penalty"):
            if k in params:
                llm_kw[k] = params[k]

        ctx_parts: list[str] = []
        if history_context:
            ctx_parts.append(f"[對話歷史]\n{history_context}")
        context = "\n\n".join(ctx_parts)

        async for token in self._llm_service.generate_stream(
            sys_prompt, user_message, context, **llm_kw
        ):
            yield {"type": "token", "content": token}

    async def process_message_stream(
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
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming: route → tool → stream LLM response."""

        if enabled_tools is not None and len(enabled_tools) == 0:
            async for evt in self._stream_direct(
                user_message, system_prompt,
                llm_params, history_context,
            ):
                yield evt
            return

        initial_state = {
            "messages": [],
            "user_message": user_message,
            "tenant_id": tenant_id,
            "kb_id": kb_id,
            "kb_ids": kb_ids or [],
            "system_prompt": system_prompt or "",
            "llm_params": llm_params or {},
            "history_context": history_context,
            "router_context": router_context,
            "current_tool": "",
            "tool_reasoning": "",
            "tool_result": {},
            "final_answer": "",
            "accumulated_usage": {},
            "enabled_tools": enabled_tools or [],
            "rag_top_k": rag_top_k,
            "rag_score_threshold": rag_score_threshold,
        }

        # Phase 1: route + tool
        tool_name = ""
        tool_result: dict[str, Any] = {}

        async for update in self._compiled_routing.astream(
            initial_state, stream_mode="updates"
        ):
            for node_name, node_output in update.items():
                if node_name == "router":
                    tool_name = node_output.get(
                        "current_tool", ""
                    )
                    yield {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "tool_name": tool_name,
                                "reasoning": node_output.get(
                                    "tool_reasoning", ""
                                ),
                            },
                        ],
                    }
                elif node_name == "rag_tool":
                    tool_result = node_output.get(
                        "tool_result", {}
                    )

        # Extract & yield sources
        if tool_name == "rag_query" and isinstance(
            tool_result, dict
        ):
            raw_sources = tool_result.get("sources", [])
            sources = [
                {
                    "document_name": s.get("document_name", ""),
                    "content_snippet": s.get(
                        "content_snippet", ""
                    ),
                    "score": s.get("score", 0.0),
                }
                for s in raw_sources
            ]
            if sources:
                yield {"type": "sources", "sources": sources}

        # Phase 2: Stream LLM response
        context = self._build_respond_context(
            initial_state.get("history_context") or "",
            tool_result,
        )

        custom_prompt = initial_state.get("system_prompt") or ""
        sys_prompt = (
            custom_prompt
            if custom_prompt.strip()
            else RESPOND_SYSTEM_PROMPT
        )
        llm_kw = _extract_llm_kwargs(initial_state)

        logger.info(
            "agent.stream.respond",
            user_message=user_message,
            tool=tool_name,
            system_prompt=sys_prompt[:100],
            context_len=len(context),
        )

        async for token in self._llm_service.generate_stream(
            sys_prompt, user_message, context, **llm_kw
        ):
            yield {"type": "token", "content": token}
