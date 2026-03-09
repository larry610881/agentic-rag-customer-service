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
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.application.agent.prompt_assembler import assemble as assemble_prompt
from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import Source
from src.infrastructure.langgraph.tools import RAGQueryTool
from src.infrastructure.llm.dynamic_llm_factory import DynamicLLMServiceProxy

logger = structlog.get_logger(__name__)


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
            """查詢知識庫回答用戶問題，適用於退貨政策、使用說明等知識型問題。

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
            return result.get("context", "") or "知識庫中沒有找到相關資訊。"

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
        from langchain_openai import ChatOpenAI
        import os

        kwargs: dict[str, Any] = {
            "model": model or "gpt-4o-mini",
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Support custom base_url for OpenAI-compatible providers
        base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url

        return ChatOpenAI(**kwargs)

    @staticmethod
    async def _load_mcp_tools_with_stack(
        stack: AsyncExitStack,
        server_url: str,
        enabled_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """Connect to MCP Server, keep session alive via exit stack.

        The session is kept open until the exit stack is closed,
        so that tool objects can call the MCP server during agent execution.
        """
        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            # Enter streamable HTTP context — kept alive by stack
            read, write, _ = await stack.enter_async_context(
                streamablehttp_client(server_url)
            )
            session = await stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            all_tools = await load_mcp_tools(session)

            if enabled_tools:
                filtered = [
                    t for t in all_tools if t.name in enabled_tools
                ]
                logger.info(
                    "react.mcp_tools_loaded",
                    total=len(all_tools),
                    filtered=len(filtered),
                    enabled=enabled_tools,
                )
                return filtered

            logger.info(
                "react.mcp_tools_loaded",
                total=len(all_tools),
            )
            return all_tools

        except Exception as exc:
            logger.warning(
                "react.mcp_tools_failed",
                server_url=server_url,
                error=str(exc),
            )
            return []

    def _build_react_graph(
        self,
        tools: list[BaseTool],
        system_prompt: str | None,
        llm: Any,
        max_tool_calls: int,
    ) -> Any:
        """Build a ReAct StateGraph with agent ↔ tools loop."""
        model_with_tools = llm.bind_tools(tools)
        call_count = 0

        async def agent_node(state: MessagesState) -> dict:
            nonlocal call_count
            messages = list(state["messages"])
            # Sanitize: some LLMs (DeepSeek) require string content,
            # but MCP ToolMessages may have list content blocks.
            for msg in messages:
                if isinstance(msg.content, list):
                    msg.content = "\n".join(
                        b.text if hasattr(b, "text") else str(b)
                        for b in msg.content
                    )
            if system_prompt:
                messages = [SystemMessage(content=system_prompt)] + messages
            response = await model_with_tools.ainvoke(messages)
            call_count += 1
            return {"messages": [response]}

        def should_continue(state: MessagesState) -> str:
            nonlocal call_count
            last = state["messages"][-1]
            if not isinstance(last, AIMessage) or not last.tool_calls:
                return END
            if call_count >= max_tool_calls:
                return END
            return "tools"

        builder = StateGraph(MessagesState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", ToolNode(tools))
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
    ) -> AgentResponse:
        async with AsyncExitStack() as stack:
            # 1. Build RAG tool
            rag_lc_tool = self._build_rag_lc_tool(
                tenant_id, kb_ids, kb_id, rag_top_k, rag_score_threshold
            )
            tools: list[BaseTool] = [rag_lc_tool]

            # 2. Load MCP tools — sessions kept alive by stack
            for server in (mcp_servers or []):
                mcp_tools = await self._load_mcp_tools_with_stack(
                    stack, server["url"], server.get("enabled_tools")
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
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream version — runs the same ReAct loop, yields events."""
        async with AsyncExitStack() as stack:
            # Build tools
            rag_lc_tool = self._build_rag_lc_tool(
                tenant_id, kb_ids, kb_id, rag_top_k, rag_score_threshold
            )
            tools: list[BaseTool] = [rag_lc_tool]

            # Load MCP tools — sessions kept alive by stack
            for server in (mcp_servers or []):
                mcp_tools = await self._load_mcp_tools_with_stack(
                    stack, server["url"], server.get("enabled_tools")
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
            )

            # Emit initial status so frontend shows "AI 分析中" immediately
            yield {"type": "status", "status": "react_thinking"}

            # Stream graph execution
            tool_calls_emitted: list[dict[str, Any]] = []
            call_count = 0

            async for event in graph.astream(
                {"messages": input_messages}, stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    if node_name == "agent":
                        messages = node_output.get("messages", [])
                        for msg in messages:
                            if isinstance(msg, AIMessage):
                                if msg.tool_calls:
                                    call_count += 1
                                    if audit_mode != "off":
                                        tc_list = []
                                        for tc in msg.tool_calls:
                                            entry: dict[str, Any] = {
                                                "tool_name": tc["name"],
                                                "reasoning": "",
                                            }
                                            if audit_mode == "full":
                                                entry["tool_input"] = tc.get("args", {})
                                                entry["iteration"] = call_count
                                            tc_list.append(entry)
                                        tool_calls_emitted.extend(tc_list)
                                        yield {
                                            "type": "tool_calls",
                                            "tool_calls": tc_list,
                                        }
                                        # Yield executing status for each tool
                                        for tc in msg.tool_calls:
                                            yield {
                                                "type": "status",
                                                "status": f"{tc['name']}_executing",
                                            }
                                elif msg.content:
                                    content = (
                                        msg.content
                                        if isinstance(msg.content, str)
                                        else str(msg.content)
                                    )
                                    yield {
                                        "type": "token",
                                        "content": content,
                                    }

                    elif node_name == "tools":
                        # Tools node completed — yield done status
                        messages = node_output.get("messages", [])
                        for msg in messages:
                            if hasattr(msg, "name") and msg.name:
                                yield {
                                    "type": "status",
                                    "status": f"{msg.name}_done",
                                }
                            # Extract sources from ToolMessage if available
                            if hasattr(msg, "content") and msg.content:
                                try:
                                    import json
                                    content = (
                                        json.loads(msg.content)
                                        if isinstance(msg.content, str)
                                        else msg.content
                                    )
                                    if isinstance(content, dict) and "sources" in content:
                                        sources = content["sources"]
                                        if sources:
                                            yield {
                                                "type": "sources",
                                                "sources": sources,
                                            }
                                except (json.JSONDecodeError, TypeError):
                                    pass

            yield {"type": "done"}

    @staticmethod
    def _parse_response(
        result: dict[str, Any],
        audit_mode: str = "minimal",
    ) -> AgentResponse:
        """Extract final answer and tool calls from graph result."""
        messages = result.get("messages", [])

        # Find the last AI message as the answer
        answer = ""
        tool_calls: list[dict[str, Any]] = []
        iteration = 0

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    iteration += 1
                    if audit_mode != "off":
                        for tc in msg.tool_calls:
                            entry: dict[str, Any] = {
                                "tool_name": tc["name"],
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
            elif isinstance(msg, ToolMessage) and audit_mode == "full":
                content = str(msg.content)[:500] if msg.content else ""
                if tool_calls:
                    tool_calls[-1]["tool_output"] = content

        if not tool_calls:
            tool_calls = [{"tool_name": "direct", "reasoning": ""}]

        return AgentResponse(
            answer=answer,
            tool_calls=tool_calls,
            sources=[],
            conversation_id=str(uuid4()),
        )
