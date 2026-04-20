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
from src.infrastructure.langgraph.dm_image_query_tool import (
    DmImageQueryTool,
)
from src.infrastructure.langgraph.transfer_to_human_tool import (
    TransferToHumanTool,
)
from src.infrastructure.langgraph.usage import (
    build_usage_event,
    extract_usage_from_langchain_messages,
)
from src.infrastructure.llm.dynamic_llm_factory import DynamicLLMServiceProxy
from src.application.agent.tool_label_resolver import resolve_tool_label
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)
from src.infrastructure.observability.tool_trace_recorder import (
    record_tool_output,
)

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
        dm_image_query_tool: DmImageQueryTool | None = None,
        transfer_to_human_tool: TransferToHumanTool | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._rag_tool = rag_tool
        self._tool_registry = tool_registry
        self._cached_tool_loader = cached_tool_loader
        self._dm_image_query_tool = dm_image_query_tool
        self._transfer_to_human_tool = transfer_to_human_tool

    def _build_rag_lc_tool(
        self,
        tenant_id: str,
        kb_ids: list[str] | None,
        kb_id: str,
        rag_top_k: int | None,
        rag_score_threshold: float | None,
        rerank_cfg: dict[str, Any] | None = None,
    ) -> BaseTool:
        """Build a LangChain BaseTool wrapping the RAG query."""
        rag_tool = self._rag_tool
        _rerank = rerank_cfg or {}

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
                rerank_enabled=_rerank.get("rerank_enabled"),
                rerank_model=_rerank.get("rerank_model"),
                rerank_top_n=_rerank.get("rerank_top_n"),
            )
            import json as _json
            return _json.dumps(result, ensure_ascii=False)

        return rag_query  # type: ignore[return-value]

    def _build_dm_image_lc_tool(
        self,
        tenant_id: str,
        kb_id: str,
        rag_top_k: int | None,
        rag_score_threshold: float | None,
        kb_ids: list[str] | None = None,
    ) -> BaseTool:
        """Build a LangChain BaseTool wrapping query_dm_with_image.

        Returns DM 子頁 PNG 圖片 URL 透過 sources 欄位（不在 context 內），
        channel handler 從 result.sources 過濾 image_url 後渲染。
        Bot 連多 KB 時傳 kb_ids，dm tool 跨 KB search 並過濾 image/* doc。
        """
        dm_tool = self._dm_image_query_tool
        _kb_ids = kb_ids

        @tool
        async def query_dm_with_image(query: str) -> str:
            """查詢家樂福 DM（型錄）知識庫並回傳對應頁面的 PNG 圖片。

            【請務必在以下情境使用本工具，勿改用 rag_query】：
            - 詢問「促銷」「優惠」「特價」「折扣」「買一送一」「便宜」「划算」
            - 詢問商品價格、目前活動、DM 內容、傳單、廣告、型錄
            - 詢問特定商品（例：衛生紙、牛奶、零食、家電、生鮮、飲料、清潔用品）
            - 任何涉及「家樂福商品」「DM」「型錄」「廣告」「特賣」的問題

            回傳結果含 context 文字描述 + sources（每筆含 image_url 的項目
            會由使用者端自動顯示圖片，**你只需用 context 文字回答即可，不要
            在回覆中嵌入或提及 URL**）。

            Args:
                query: 要查詢的商品或活動關鍵字（例：「衛生紙促銷」「鳳梨價格」）
            """
            assert dm_tool is not None, "dm_image_query_tool not injected"
            result = await dm_tool.invoke(
                tenant_id=tenant_id,
                kb_id=kb_id,
                kb_ids=_kb_ids,
                query=query,
                top_k=rag_top_k if rag_top_k is not None else 5,
                score_threshold=(
                    rag_score_threshold
                    if rag_score_threshold is not None
                    else 0.3
                ),
            )
            import json as _json
            return _json.dumps(result, ensure_ascii=False)

        return query_dm_with_image  # type: ignore[return-value]

    def _build_transfer_to_human_lc_tool(
        self,
        customer_service_url: str,
    ) -> BaseTool:
        """Build a LangChain tool that returns the configured contact card.

        The tool output is serialized JSON; channel handlers look for the
        ``contact`` key to render a button / Flex message.
        """
        transfer_tool = self._transfer_to_human_tool

        @tool
        async def transfer_to_human_agent(reason: str = "") -> str:
            """轉接真人客服 / transfer to human customer service agent.

            當下列情境時呼叫本工具：
            - 使用者明確要求轉人工（「要找真人」「轉客服」「叫主管來」）
            - 使用者情緒激動、多次表達不滿或投訴
            - 複雜退換貨 / 帳務爭議 / 需核對訂單明細等知識庫無法處理的議題
            - 使用者連問 2 次以上仍未解決問題時

            回傳含 context 文字訊息與 contact 聯絡按鈕（由使用者端自動顯示）。
            **你只需用 context 文字回答，不要在回覆中嵌入或提及 URL / 電話。**

            Args:
                reason: （選填）轉接原因，會附加在回覆文字裡給使用者看
            """
            assert transfer_tool is not None, (
                "transfer_to_human_tool not injected"
            )
            result = await transfer_tool.invoke(
                customer_service_url=customer_service_url,
                reason=reason,
            )
            import json as _json
            return _json.dumps(result, ensure_ascii=False)

        return transfer_to_human_agent  # type: ignore[return-value]

    @staticmethod
    def _resolve_enabled_tools(
        enabled_tools: list[str] | None,
    ) -> set[str]:
        """Resolve effective tool name set.

        - None → backward compatible default {"rag_query"}
        - [] → 顯式空（不啟用任何內建 tool）
        - list → 該 list 為準
        """
        if enabled_tools is None:
            return {"rag_query"}
        return set(enabled_tools)

    def _build_builtin_tools(
        self,
        *,
        tenant_id: str,
        kb_id: str,
        kb_ids: list[str] | None,
        enabled_tools: list[str] | None,
        rag_top_k: int | None,
        rag_score_threshold: float | None,
        metadata: dict[str, Any] | None,
        tool_rag_params: dict[str, dict[str, Any]] | None,
        customer_service_url: str = "",
    ) -> list[BaseTool]:
        """Build built-in RAG tools with per-tool parameter overrides.

        Per-tool params in ``tool_rag_params`` take precedence over the
        legacy flat args (``rag_top_k``/``rag_score_threshold``/``metadata``).
        """
        tools: list[BaseTool] = []
        effective = self._resolve_enabled_tools(enabled_tools)
        _metadata = metadata or {}

        def _params_for(tool_name: str) -> dict[str, Any]:
            per = (tool_rag_params or {}).get(tool_name) or {}
            return {
                "rag_top_k": per.get("rag_top_k", rag_top_k),
                "rag_score_threshold": per.get(
                    "rag_score_threshold", rag_score_threshold
                ),
                "rerank_enabled": per.get(
                    "rerank_enabled", _metadata.get("rerank_enabled")
                ),
                "rerank_model": per.get(
                    "rerank_model", _metadata.get("rerank_model")
                ),
                "rerank_top_n": per.get(
                    "rerank_top_n", _metadata.get("rerank_top_n")
                ),
            }

        if "rag_query" in effective and (kb_id or kb_ids):
            params = _params_for("rag_query")
            tools.append(
                self._build_rag_lc_tool(
                    tenant_id, kb_ids, kb_id,
                    params["rag_top_k"], params["rag_score_threshold"],
                    rerank_cfg={
                        "rerank_enabled": params["rerank_enabled"],
                        "rerank_model": params["rerank_model"],
                        "rerank_top_n": params["rerank_top_n"],
                    },
                )
            )
        if (
            "query_dm_with_image" in effective
            and kb_id
            and self._dm_image_query_tool is not None
        ):
            params = _params_for("query_dm_with_image")
            tools.append(
                self._build_dm_image_lc_tool(
                    tenant_id, kb_id,
                    params["rag_top_k"], params["rag_score_threshold"],
                    kb_ids=kb_ids,
                )
            )
        if (
            "transfer_to_human_agent" in effective
            and self._transfer_to_human_tool is not None
        ):
            tools.append(
                self._build_transfer_to_human_lc_tool(customer_service_url)
            )
        return tools

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
            # 對 LiteLLM connection / DNS flake 做重試，避免 webhook timeout
            "max_retries": 3,
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
        # Track last agent_llm node_id for parent linking
        last_agent_node_id: str = ""

        async def agent_node(state: MessagesState) -> dict:
            nonlocal call_count, last_agent_node_id
            call_count += 1
            t0 = time.monotonic()
            trace_start_ms = AgentTraceCollector.offset_ms()

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
            trace_end_ms = AgentTraceCollector.offset_ms()

            # Extract token usage from response
            node_token_usage = None
            has_usage = (
                isinstance(response, AIMessage)
                and hasattr(response, "usage_metadata")
                and response.usage_metadata
            )
            if has_usage:
                um = response.usage_metadata
                node_token_usage = {
                    "input_tokens": um.get("input_tokens", 0),
                    "output_tokens": um.get("output_tokens", 0),
                }
                model_name = ""
                if hasattr(response, "response_metadata"):
                    model_name = response.response_metadata.get("model_name", "")
                if model_name:
                    node_token_usage["model"] = model_name

            # Build llm_input/output for trace
            llm_input_text = "\n---\n".join(
                f"[{type(m).__name__}] {m.content if isinstance(m.content, str) else str(m.content)}"
                for m in messages
            )
            llm_output_text = (
                response.content
                if isinstance(response, AIMessage) and isinstance(response.content, str)
                else str(getattr(response, "content", ""))
            )

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
                last_agent_node_id = AgentTraceCollector.add_node(
                    node_type="agent_llm",
                    label=f"ReAct 迭代 {call_count}",
                    parent_id=None,
                    start_ms=trace_start_ms,
                    end_ms=trace_end_ms,
                    token_usage=node_token_usage,
                    iteration=call_count,
                    decision="tool_call",
                    tool_calls=[tc["name"] for tc in response.tool_calls],
                    llm_input=llm_input_text,
                    llm_output=str(response.tool_calls),
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
                last_agent_node_id = AgentTraceCollector.add_node(
                    node_type="agent_llm",
                    label=f"ReAct 迭代 {call_count} (回覆)",
                    parent_id=None,
                    start_ms=trace_start_ms,
                    end_ms=trace_end_ms,
                    token_usage=node_token_usage,
                    iteration=call_count,
                    decision="final_answer",
                    answer_preview=content_preview,
                    llm_input=llm_input_text,
                    llm_output=llm_output_text,
                )

            return {"messages": [response]}

        _tool_node = ToolNode(tools, handle_tool_errors=True)

        async def tools_node(state: MessagesState) -> dict:
            """Wraps ToolNode with logging."""
            import time

            t0 = time.monotonic()
            trace_start_ms = AgentTraceCollector.offset_ms()
            last_msg = state["messages"][-1]
            tool_names = []
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                tool_names = [tc["name"] for tc in last_msg.tool_calls]

            logger.info(
                "react.tools_node.start",
                tools=tool_names,
            )

            # Pre-register tool trace nodes so inner nodes can be children
            tool_node_ids: dict[str, str] = {}
            for tn in tool_names:
                nid = AgentTraceCollector.add_node(
                    node_type="tool_call",
                    label=tn,
                    parent_id=None,
                    start_ms=trace_start_ms,
                    end_ms=trace_start_ms,  # placeholder, updated below
                    tool_name=tn,
                )
                tool_node_ids[tn] = nid
                # Set as parent so inner nodes (RAG search, rerank) become children
                AgentTraceCollector.set_tool_parent(nid)

            result = await _tool_node.ainvoke(state)

            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            trace_end_ms = AgentTraceCollector.offset_ms()
            AgentTraceCollector.clear_tool_parent()

            # Update tool trace nodes with final timing + result
            trace = AgentTraceCollector.current()
            for msg in result.get("messages", []):
                if isinstance(msg, ToolMessage):
                    content_str = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    tool_name = getattr(msg, "name", "unknown")
                    logger.info(
                        "react.tools_node.result",
                        tool_name=tool_name,
                        elapsed_ms=elapsed_ms,
                        result_length=len(content_str),
                        result_preview=content_str[:200],
                    )
                    # Update pre-registered node with result data
                    nid = tool_node_ids.get(tool_name)
                    if trace and nid:
                        for node in trace.nodes:
                            if node.node_id == nid:
                                node.end_ms = trace_end_ms
                                node.duration_ms = round(
                                    trace_end_ms - node.start_ms, 1
                                )
                                node.metadata["result_length"] = len(
                                    content_str
                                )
                                node.metadata["result_preview"] = content_str
                                record_tool_output(node, content_str)
                                break

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
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        bot_id: str = "",
    ) -> AgentResponse:
        # Start agent trace
        _llm_params = llm_params or {}
        AgentTraceCollector.start(
            tenant_id, "react",
            llm_model=_llm_params.get("model", ""),
            llm_provider=_llm_params.get("provider_name", ""),
            bot_id=bot_id or None,
        )
        history_len = len(history) if history else 0
        AgentTraceCollector.add_node(
            "user_input", "使用者輸入", None, 0.0, 0.0,
            message_preview=user_message[:200],
            history_turns=history_len,
            has_history_context=bool(history_context),
            history_context=history_context or "",
        )
        # Worker routing breadcrumb（Supervisor 模式才有；由 send_message_use_case 塞入 metadata）
        _wr_info = (metadata or {}).get("_worker_routing")
        if isinstance(_wr_info, dict) and _wr_info.get("name"):
            AgentTraceCollector.add_node(
                "worker_routing",
                f"已分流至 Worker：{_wr_info['name']}",
                None, 0.0, 0.0,
                worker_name=_wr_info["name"],
                worker_llm=_wr_info.get("llm_model") or "(default)",
                worker_llm_provider=_wr_info.get("llm_provider") or "",
                worker_kb_count=_wr_info.get("kb_count", 0),
            )

        async with AsyncExitStack() as stack:
            # 1. Build built-in tools (per-tool params override flat args)
            tools: list[BaseTool] = self._build_builtin_tools(
                tenant_id=tenant_id,
                kb_id=kb_id,
                kb_ids=kb_ids,
                enabled_tools=enabled_tools,
                rag_top_k=rag_top_k,
                rag_score_threshold=rag_score_threshold,
                metadata=metadata,
                tool_rag_params=tool_rag_params,
                customer_service_url=customer_service_url,
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

            # Trace: final_response node
            end_ms = AgentTraceCollector.offset_ms()
            AgentTraceCollector.add_node(
                "final_response", "最終回覆", None, end_ms, end_ms,
            )

            # 5. Parse response
            return self._parse_response(result)

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
        call_count: int,
        tool_calls_emitted: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Handle an AIMessage with tool_calls from the agent node.

        Returns events to yield. Mutates tool_calls_emitted in place.
        """
        events: list[dict[str, Any]] = []
        tc_list: list[dict[str, Any]] = []
        for tc in msg.tool_calls:
            entry: dict[str, Any] = {
                "tool_name": tc["name"],
                "label": resolve_tool_label(tc["name"]),
                "tool_call_id": tc.get("id", ""),
                "reasoning": "",
                "tool_input": tc.get("args", {}),
                "iteration": call_count,
            }
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
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        bot_id: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream version — runs the same ReAct loop, yields events."""
        async with AsyncExitStack() as stack:
            # Build built-in tools (per-tool params override flat args)
            tools: list[BaseTool] = self._build_builtin_tools(
                tenant_id=tenant_id,
                kb_id=kb_id,
                kb_ids=kb_ids,
                enabled_tools=enabled_tools,
                rag_top_k=rag_top_k,
                rag_score_threshold=rag_score_threshold,
                metadata=metadata,
                tool_rag_params=tool_rag_params,
                customer_service_url=customer_service_url,
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

            # Start agent trace
            history_len = len(history) if history else 0
            _llm_params_s = llm_params or {}
            AgentTraceCollector.start(
                tenant_id, "react",
                llm_model=_llm_params_s.get("model", ""),
                llm_provider=_llm_params_s.get("provider_name", ""),
                bot_id=bot_id or None,
            )
            AgentTraceCollector.add_node(
                "user_input", "使用者輸入", None, 0.0, 0.0,
                message_preview=user_message[:200],
                history_turns=history_len,
                has_history_context=bool(history_context),
                history_context=history_context or "",
            )
            # Worker routing breadcrumb
            _wr_info_s = (metadata or {}).get("_worker_routing")
            _wr_event: dict[str, Any] | None = None
            if isinstance(_wr_info_s, dict) and _wr_info_s.get("name"):
                AgentTraceCollector.add_node(
                    "worker_routing",
                    f"已分流至 Worker：{_wr_info_s['name']}",
                    None, 0.0, 0.0,
                    worker_name=_wr_info_s["name"],
                    worker_llm=_wr_info_s.get("llm_model") or "(default)",
                    worker_llm_provider=_wr_info_s.get("llm_provider") or "",
                    worker_kb_count=_wr_info_s.get("kb_count", 0),
                )
                # Phase 1: 讓 Studio canvas 知道路由到哪個 worker（藍圖點亮對應卡片）
                _wr_event = {
                    "type": "worker_routing",
                    "worker_name": _wr_info_s["name"],
                    "worker_llm": _wr_info_s.get("llm_model") or "(default)",
                    "worker_llm_provider": _wr_info_s.get("llm_provider") or "",
                    "worker_kb_count": _wr_info_s.get("kb_count", 0),
                }

            # Phase 1: 統一附加 node_id + ts_ms 到每個 stream event；
            # 讓前端 Studio canvas 用 node_id 精準對應 trace 節點，取代 MVP 的字串啟發式。
            def _ev(d: dict[str, Any]) -> dict[str, Any]:
                d.setdefault("node_id", AgentTraceCollector.last_node_id())
                d.setdefault("ts_ms", round(AgentTraceCollector.offset_ms(), 1))
                return d

            if _wr_event is not None:
                yield _ev(_wr_event)

            # Emit initial status so frontend shows "AI 分析中" immediately
            yield _ev({"type": "status", "status": "react_thinking"})

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
                                yield _ev(ev)

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
                                                    call_count,
                                                    tool_calls_emitted,
                                                ):
                                                    yield _ev(ev)
                                            elif msg.content:
                                                # Fallback: if messages mode didn't
                                                # stream tokens (e.g. mock LLM without
                                                # astream), emit content as one chunk.
                                                if not llm_generating_emitted:
                                                    yield _ev({
                                                        "type": "status",
                                                        "status": "llm_generating",
                                                    })
                                                    content = (
                                                        msg.content
                                                        if isinstance(
                                                            msg.content, str
                                                        )
                                                        else str(msg.content)
                                                    )
                                                    yield _ev({
                                                        "type": "token",
                                                        "content": content,
                                                    })
                                                llm_generating_emitted = False

                                elif node_name == "tools":
                                    messages = node_output.get("messages", [])
                                    for msg in messages:
                                        if hasattr(msg, "name") and msg.name:
                                            yield _ev({
                                                "type": "status",
                                                "status": f"{msg.name}_done",
                                            })
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
                                                        yield _ev({
                                                            "type": "sources",
                                                            "sources": sources,
                                                        })
                                                        _emitted_sources = True
                                                # transfer_to_human_agent tool → emit contact event
                                                if (
                                                    isinstance(content, dict)
                                                    and content.get("contact")
                                                ):
                                                    yield _ev({
                                                        "type": "contact",
                                                        "contact": content["contact"],
                                                    })
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
                                                        yield _ev({
                                                            "type": "sources",
                                                            "sources": rag_sources,
                                                        })
                                    yield _ev({
                                        "type": "status",
                                        "status": "react_thinking",
                                    })
            except asyncio.TimeoutError:
                timeout_s = _settings.agent_stream_timeout
                logger.error(
                    "react.stream.timeout", timeout_s=timeout_s
                )
                # Phase 1: 失敗節點寫入 trace（outcome=failed），讓 Studio 紅框可見
                _err_msg = f"Agent 回應逾時（{timeout_s}s），請縮短問題或更換模型"
                _err_ms = AgentTraceCollector.offset_ms()
                AgentTraceCollector.add_node(
                    "agent_llm",
                    "agent timeout",
                    None,
                    _err_ms,
                    _err_ms,
                    outcome="failed",
                    error_message=_err_msg,
                )
                yield _ev({"type": "error", "message": _err_msg})

            # Trace: final_response node
            end_ms = AgentTraceCollector.offset_ms()
            AgentTraceCollector.add_node(
                "final_response", "最終回覆", None, end_ms, end_ms,
            )

            # Yield usage event before done
            usage_event = build_usage_event(
                extract_usage_from_langchain_messages(all_ai_messages)
            )
            if usage_event:
                yield _ev(usage_event)

            yield _ev({"type": "done"})

    @staticmethod
    def _parse_response(
        result: dict[str, Any],
    ) -> AgentResponse:
        """Extract final answer and tool calls from graph result."""
        import json as _json

        messages = result.get("messages", [])

        # Find the last AI message as the answer
        answer = ""
        tool_calls: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        contact: dict[str, Any] | None = None
        iteration = 0

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    iteration += 1
                    for tc in msg.tool_calls:
                        entry: dict[str, Any] = {
                            "tool_name": tc["name"],
                            "label": resolve_tool_label(tc["name"]),
                            "tool_call_id": tc.get("id", ""),
                            "reasoning": "",
                            "tool_input": tc.get("args", {}),
                            "iteration": iteration,
                        }
                        tool_calls.append(entry)
                elif msg.content:
                    answer = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
            elif isinstance(msg, ToolMessage):
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
                        # transfer_to_human_agent tool → capture contact
                        if isinstance(parsed, dict) and parsed.get("contact"):
                            contact = parsed["contact"]
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
            contact=contact,
        )
