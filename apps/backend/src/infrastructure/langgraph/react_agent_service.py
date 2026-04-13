"""ReActAgentService — ReAct Agent (RAG + MCP Tools) 實作

使用 LangGraph StateGraph 建立 agent ↔ tools 迴圈，
支援 RAG 知識庫查詢和 MCP 外部工具呼叫。
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any
from uuid import uuid4

import structlog
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from src.application.agent.prompt_assembler import assemble as assemble_prompt
from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.domain.rag.services import LLMService
from src.infrastructure.langgraph.tools import RAGQueryTool
from src.infrastructure.langgraph.usage import (
    build_usage_event,
    extract_usage_from_langchain_messages,
)
from src.infrastructure.llm.dynamic_llm_factory import DynamicLLMServiceProxy

logger = structlog.get_logger(__name__)


def _backfill_tool_output(
    tool_calls_emitted: list[dict[str, Any]],
    msg: Any,
    content_str: str,
) -> None:
    """Match a ToolMessage to its tool_call entry and backfill output.

    Tries tool_call_id match first (precise), falls back to tool_name (legacy).
    """
    msg_tc_id = getattr(msg, "tool_call_id", "") or ""

    # 1. Try precise match by tool_call_id
    if msg_tc_id:
        for tc in tool_calls_emitted:
            if tc.get("tool_call_id") == msg_tc_id and "tool_output" not in tc:
                tc["tool_output"] = content_str
                return

    # 2. Fallback: match by tool_name (backward compatibility)
    tool_name = getattr(msg, "name", "") or ""
    if tool_name:
        for tc in reversed(tool_calls_emitted):
            if tc.get("tool_name") == tool_name and "tool_output" not in tc:
                tc["tool_output"] = content_str
                return


class ReActAgentService(AgentService):
    def __init__(
        self,
        llm_service: LLMService,
        rag_tool: RAGQueryTool,
        tool_registry: Any | None = None,
        cached_tool_loader: Any | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._rag_tool = rag_tool
        self._tool_registry = tool_registry
        self._cached_tool_loader = cached_tool_loader

    def _build_rag_lc_tool(
        self,
        tenant_id: str,
        kb_ids: list[str] | None,
        kb_id: str,
        rag_top_k: int | None,
        rag_score_threshold: float | None,
    ) -> BaseTool:
        """Build a LangChain BaseTool wrapping the RAG query."""
        rag_tool = self._rag_tool

        @tool
        async def rag_query(query: str) -> str:
            """查詢知識庫回答用戶問題。適用於：商品推薦、分類導覽、退貨政策、使用說明、品牌介紹等需要綜合判斷的問題。當用戶問「推薦」「適合」「有什麼」「哪些」類問題時優先使用此工具。

            Args:
                query: 要查詢的問題
            """
            result = await rag_tool.invoke(
                tenant_id=tenant_id,
                kb_id=kb_id,
                query=query,
                kb_ids=kb_ids,
                top_k=rag_top_k,
                score_threshold=rag_score_threshold,
            )
            import json as _json
            return _json.dumps(result, ensure_ascii=False)

        return rag_query  # type: ignore[return-value]

    async def _resolve_llm_model(
        self, llm_params: dict[str, Any] | None
    ) -> Any:
        """Resolve LangChain ChatModel for the request."""
        params = llm_params or {}
        provider = params.get("provider_name", "")
        model = params.get("model", "")
        temperature = params.get("temperature", 0.7)
        max_tokens = params.get("max_tokens", 1024)

        # Try dynamic resolution first
        if isinstance(self._llm_service, DynamicLLMServiceProxy) and provider:
            service = await self._llm_service.resolve_for_bot(
                provider_name=provider, model=model,
            )
            # Try to get a LangChain ChatModel from the service
            if hasattr(service, "get_chat_model"):
                return service.get_chat_model(
                    temperature=temperature, max_tokens=max_tokens,
                )

        # Fallback: create ChatModel from provider/model directly
        return self._create_chat_model(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @staticmethod
    def _create_chat_model(
        provider: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Any:
        """Create a LangChain ChatModel from provider and model name."""
        if provider in ("anthropic", "claude"):
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model or "claude-sonnet-4-20250514",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # Default to OpenAI-compatible
        import os

        from langchain_openai import ChatOpenAI

        from src.config import settings

        kwargs: dict[str, Any] = {
            "model": model or "gpt-4o-mini",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "request_timeout": settings.agent_llm_request_timeout,
        }

        # Support custom base_url for OpenAI-compatible providers
        base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url

        return ChatOpenAI(**kwargs)

    def _build_react_graph(
        self,
        tools: list[BaseTool],
        system_prompt: str | None,
        llm: Any,
        max_tool_calls: int,
    ) -> Any:
        """Build a ReAct StateGraph with agent ↔ tools loop."""
        import time

        model_with_tools = llm.bind_tools(tools)
        call_count = 0

        async def agent_node(state: MessagesState) -> dict:
            nonlocal call_count
            call_count += 1
            t0 = time.monotonic()

            messages = list(state["messages"])
            # Sanitize: some LLMs (DeepSeek) require string content,
            # but MCP ToolMessages may have list content blocks.
            for msg in messages:
                if isinstance(msg.content, list):
                    msg.content = "\n".join(
                        b.text if hasattr(b, "text") else str(b)
                        for b in msg.content
                    )

            logger.info(
                "react.agent_node.start",
                iteration=call_count,
                message_count=len(messages),
            )

            if system_prompt:
                messages = [SystemMessage(content=system_prompt)] + messages
            response = await model_with_tools.ainvoke(messages)

            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

            if isinstance(response, AIMessage) and response.tool_calls:
                tc_summary = [
                    {
                        "name": tc["name"],
                        "args_keys": list(tc.get("args", {}).keys()),
                    }
                    for tc in response.tool_calls
                ]
                logger.info(
                    "react.agent_node.tool_calls",
                    iteration=call_count,
                    elapsed_ms=elapsed_ms,
                    tool_calls=tc_summary,
                )
            else:
                content_preview = ""
                if isinstance(response, AIMessage) and response.content:
                    content_preview = (
                        response.content[:100]
                        if isinstance(response.content, str)
                        else str(response.content)[:100]
                    )
                logger.info(
                    "react.agent_node.final_answer",
                    iteration=call_count,
                    elapsed_ms=elapsed_ms,
                    answer_preview=content_preview,
                )

            return {"messages": [response]}

        _tool_node = ToolNode(tools, handle_tool_errors=True)

        async def tools_node(state: MessagesState) -> dict:
            """Wraps ToolNode with logging."""
            import time

            t0 = time.monotonic()
            last_msg = state["messages"][-1]
            tool_names = []
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                tool_names = [tc["name"] for tc in last_msg.tool_calls]

            logger.info(
                "react.tools_node.start",
                tools=tool_names,
            )

            result = await _tool_node.ainvoke(state)

            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

            # Log each tool result summary
            for msg in result.get("messages", []):
                if isinstance(msg, ToolMessage):
                    content_str = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    logger.info(
                        "react.tools_node.result",
                        tool_name=getattr(msg, "name", "unknown"),
                        elapsed_ms=elapsed_ms,
                        result_length=len(content_str),
                        result_preview=content_str[:200],
                    )

            return result

        def should_continue(state: MessagesState) -> str:
            nonlocal call_count
            last = state["messages"][-1]
            if not isinstance(last, AIMessage) or not last.tool_calls:
                return END
            if call_count >= max_tool_calls:
                logger.warning(
                    "react.max_tool_calls_reached",
                    max_tool_calls=max_tool_calls,
                )
                return END
            return "tools"

        builder = StateGraph(MessagesState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", tools_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent", should_continue, {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "agent")
        return builder.compile()

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
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        audit_mode: str = "minimal",
        bot_id: str = "",
    ) -> AgentResponse:
        async with AsyncExitStack() as stack:
            # 1. Build knowledge tool
            tools: list[BaseTool] = []
            tools.append(
                    self._build_rag_lc_tool(
                        tenant_id, kb_ids, kb_id, rag_top_k, rag_score_threshold
                    )
                )

            # 2. Load MCP tools — sessions kept alive by stack
            if self._cached_tool_loader:
                for server in (mcp_servers or []):
                    mcp_tools = await self._cached_tool_loader.load_tools(
                        stack, server, server.get("enabled_tools")
                    )
                    tools.extend(mcp_tools)

            # 3. Resolve LLM
            llm = await self._resolve_llm_model(llm_params)

            # 4. Build and execute ReAct graph
            assembled_prompt = system_prompt or assemble_prompt("", "react")
            graph = self._build_react_graph(
                tools, assembled_prompt, llm, max_tool_calls
            )

            # Build input messages
            input_messages: list = []
            if history_context:
                input_messages.append(
                    SystemMessage(content=f"[對話歷史]\n{history_context}")
                )
            input_messages.append(HumanMessage(content=user_message))

            logger.info(
                "react.process_message",
                tenant_id=tenant_id,
                tool_count=len(tools),
                tool_names=[t.name for t in tools],
                mcp_server_count=len(mcp_servers or []),
            )

            result = await graph.ainvoke({"messages": input_messages})

            # 5. Parse response
            return self._parse_response(result, audit_mode=audit_mode)

    @staticmethod
    def _handle_text_chunk(
        msg_chunk: AIMessageChunk,
        metadata: dict[str, Any],
        llm_generating_emitted: bool,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Handle a streaming text chunk from the LLM.

        Returns (events_to_yield, updated_llm_generating_emitted).
        """
        events: list[dict[str, Any]] = []
        if metadata.get("langgraph_node") != "agent":
            return events, llm_generating_emitted
        if not isinstance(msg_chunk, AIMessageChunk):
            return events, llm_generating_emitted
        if msg_chunk.content:
            if not llm_generating_emitted:
                events.append({"type": "status", "status": "llm_generating"})
                llm_generating_emitted = True
            content = (
                msg_chunk.content
                if isinstance(msg_chunk.content, str)
                else str(msg_chunk.content)
            )
            events.append({"type": "token", "content": content})
        return events, llm_generating_emitted

    @staticmethod
    def _handle_tool_call_chunk(
        msg: AIMessage,
        audit_mode: str,
        call_count: int,
        tool_calls_emitted: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Handle an AIMessage with tool_calls from the agent node.

        Returns events to yield. Mutates tool_calls_emitted in place.
        """
        events: list[dict[str, Any]] = []
        if audit_mode != "off":
            tc_list: list[dict[str, Any]] = []
            for tc in msg.tool_calls:
                entry: dict[str, Any] = {
                    "tool_name": tc["name"],
                    "tool_call_id": tc.get("id", ""),
                    "reasoning": "",
                }
                if audit_mode == "full":
                    entry["tool_input"] = tc.get("args", {})
                    entry["iteration"] = call_count
                tc_list.append(entry)
            tool_calls_emitted.extend(tc_list)
            events.append({"type": "tool_calls", "tool_calls": tc_list})
            for tc in msg.tool_calls:
                events.append({
                    "type": "status",
                    "status": f"{tc['name']}_executing",
                })
        return events

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
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        audit_mode: str = "minimal",
        bot_id: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream version — runs the same ReAct loop, yields events."""
        async with AsyncExitStack() as stack:
            # Build knowledge tool
            tools: list[BaseTool] = []
            tools.append(
                self._build_rag_lc_tool(
                    tenant_id, kb_ids, kb_id, rag_top_k, rag_score_threshold
                )
            )

            # Load MCP tools — sessions kept alive by stack
            if self._cached_tool_loader:
                for server in (mcp_servers or []):
                    mcp_tools = await self._cached_tool_loader.load_tools(
                        stack, server, server.get("enabled_tools")
                    )
                    tools.extend(mcp_tools)

            llm = await self._resolve_llm_model(llm_params)
            assembled_prompt = system_prompt or assemble_prompt("", "react")
            graph = self._build_react_graph(
                tools, assembled_prompt, llm, max_tool_calls
            )

            input_messages: list = []
            if history_context:
                input_messages.append(
                    SystemMessage(content=f"[對話歷史]\n{history_context}")
                )
            input_messages.append(HumanMessage(content=user_message))

            logger.info(
                "react.process_message_stream",
                tenant_id=tenant_id,
                tool_count=len(tools),
                tool_names=[t.name for t in tools],
                mcp_server_count=len(mcp_servers or []),
            )

            # Emit initial status so frontend shows "AI 分析中" immediately
            yield {"type": "status", "status": "react_thinking"}

            # Stream graph execution with dual mode:
            #   "messages" → per-token LLM streaming
            #   "updates"  → node completions (tool_calls, tool results, sources)
            tool_calls_emitted: list[dict[str, Any]] = []
            call_count = 0
            llm_generating_emitted = False
            all_ai_messages: list[AIMessage] = []

            import asyncio

            from src.config import settings as _settings

            try:
                async with asyncio.timeout(_settings.agent_stream_timeout):
                    async for event in graph.astream(
                        {"messages": input_messages},
                        stream_mode=["messages", "updates"],
                    ):
                        mode, data = event

                        if mode == "messages":
                            msg_chunk, chunk_meta = data
                            events, llm_generating_emitted = (
                                self._handle_text_chunk(
                                    msg_chunk,
                                    chunk_meta,
                                    llm_generating_emitted,
                                )
                            )
                            for ev in events:
                                yield ev

                        elif mode == "updates":
                            for node_name, node_output in data.items():
                                if node_name == "agent":
                                    messages = node_output.get("messages", [])
                                    for msg in messages:
                                        if isinstance(msg, AIMessage):
                                            all_ai_messages.append(msg)
                                            if msg.tool_calls:
                                                call_count += 1
                                                llm_generating_emitted = False
                                                for ev in self._handle_tool_call_chunk(
                                                    msg,
                                                    audit_mode,
                                                    call_count,
                                                    tool_calls_emitted,
                                                ):
                                                    yield ev
                                            elif msg.content:
                                                # Fallback: if messages mode didn't
                                                # stream tokens (e.g. mock LLM without
                                                # astream), emit content as one chunk.
                                                if not llm_generating_emitted:
                                                    yield {
                                                        "type": "status",
                                                        "status": "llm_generating",
                                                    }
                                                    content = (
                                                        msg.content
                                                        if isinstance(
                                                            msg.content, str
                                                        )
                                                        else str(msg.content)
                                                    )
                                                    yield {
                                                        "type": "token",
                                                        "content": content,
                                                    }
                                                llm_generating_emitted = False

                                elif node_name == "tools":
                                    messages = node_output.get("messages", [])
                                    for msg in messages:
                                        if hasattr(msg, "name") and msg.name:
                                            yield {
                                                "type": "status",
                                                "status": f"{msg.name}_done",
                                            }
                                        # Backfill tool_output to tool_calls_emitted
                                        if (
                                            hasattr(msg, "content")
                                            and msg.content
                                            and hasattr(msg, "name")
                                            and msg.name
                                        ):
                                            content_str = (
                                                str(msg.content)[:500]
                                                if msg.content
                                                else ""
                                            )
                                            _backfill_tool_output(
                                                tool_calls_emitted,
                                                msg,
                                                content_str,
                                            )
                                        # Extract sources from tool results
                                        if hasattr(msg, "content") and msg.content:
                                            _emitted_sources = False
                                            # 1. JSON parse (MCP tools)
                                            try:
                                                import json

                                                content = (
                                                    json.loads(msg.content)
                                                    if isinstance(msg.content, str)
                                                    else msg.content
                                                )
                                                if (
                                                    isinstance(content, dict)
                                                    and "sources" in content
                                                ):
                                                    sources = content["sources"]
                                                    if sources:
                                                        yield {
                                                            "type": "sources",
                                                            "sources": sources,
                                                        }
                                                        _emitted_sources = True
                                            except (json.JSONDecodeError, TypeError):
                                                pass
                                            # 2. rag_query plain text → chunks
                                            if (
                                                not _emitted_sources
                                                and hasattr(msg, "name")
                                                and msg.name == "rag_query"
                                            ):
                                                ctx = (
                                                    msg.content
                                                    if isinstance(msg.content, str)
                                                    else str(msg.content)
                                                )
                                                _no_result = "知識庫中沒有找到相關資訊"
                                                if (
                                                    ctx.strip()
                                                    and _no_result not in ctx
                                                ):
                                                    rag_sources = [
                                                        {
                                                            "content_snippet": c.strip(),  # noqa: E501
                                                            "source": "rag_query",
                                                        }
                                                        for c in ctx.split("\n---\n")
                                                        if c.strip()
                                                    ]
                                                    if rag_sources:
                                                        yield {
                                                            "type": "sources",
                                                            "sources": rag_sources,
                                                        }
                                    yield {
                                        "type": "status",
                                        "status": "react_thinking",
                                    }
            except asyncio.TimeoutError:
                timeout_s = _settings.agent_stream_timeout
                logger.error(
                    "react.stream.timeout", timeout_s=timeout_s
                )
                yield {
                    "type": "error",
                    "message": (
                        f"Agent 回應逾時（{timeout_s}s）"
                        "，請縮短問題或更換模型"
                    ),
                }

            # Yield usage event before done
            usage_event = build_usage_event(
                extract_usage_from_langchain_messages(all_ai_messages)
            )
            if usage_event:
                yield usage_event

            yield {"type": "done"}

    @staticmethod
    def _parse_response(
        result: dict[str, Any],
        audit_mode: str = "minimal",
    ) -> AgentResponse:
        """Extract final answer and tool calls from graph result."""
        import json as _json

        messages = result.get("messages", [])

        # Find the last AI message as the answer
        answer = ""
        tool_calls: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        iteration = 0

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    iteration += 1
                    if audit_mode != "off":
                        for tc in msg.tool_calls:
                            entry: dict[str, Any] = {
                                "tool_name": tc["name"],
                                "tool_call_id": tc.get("id", ""),
                                "reasoning": "",
                            }
                            if audit_mode == "full":
                                entry["tool_input"] = tc.get("args", {})
                                entry["iteration"] = iteration
                            tool_calls.append(entry)
                elif msg.content:
                    answer = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
            elif isinstance(msg, ToolMessage):
                if audit_mode == "full":
                    content = str(msg.content)[:500] if msg.content else ""
                    _backfill_tool_output(tool_calls, msg, content)
                # Extract sources from tool results
                if hasattr(msg, "content") and msg.content:
                    _found = False
                    # 1. Try JSON (MCP tools)
                    try:
                        parsed = (
                            _json.loads(msg.content)
                            if isinstance(msg.content, str)
                            else msg.content
                        )
                        if isinstance(parsed, dict) and parsed.get("sources"):
                            sources.extend(parsed["sources"])
                            _found = True
                    except (_json.JSONDecodeError, TypeError):
                        pass
                    # 2. rag_query plain text — split into chunks
                    if (
                        not _found
                        and hasattr(msg, "name")
                        and msg.name == "rag_query"
                    ):
                        ctx = (
                            msg.content
                            if isinstance(msg.content, str)
                            else str(msg.content)
                        )
                        _no_result = "知識庫中沒有找到相關資訊"
                        if ctx.strip() and _no_result not in ctx:
                            for c in ctx.split("\n---\n"):
                                if c.strip():
                                    sources.append({
                                        "content_snippet": c.strip(),
                                        "source": "rag_query",
                                    })

        if not tool_calls:
            tool_calls = [{"tool_name": "direct", "reasoning": ""}]

        usage = extract_usage_from_langchain_messages(messages)

        return AgentResponse(
            answer=answer,
            tool_calls=tool_calls,
            sources=sources,
            conversation_id=str(uuid4()),
            usage=usage,
        )
