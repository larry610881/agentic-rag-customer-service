"""LangGraph Agent StateGraph 建構"""

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.domain.rag.services import LLMService
from src.infrastructure.langgraph.tools import (
    OrderLookupTool,
    ProductSearchTool,
    RAGQueryTool,
    TicketCreationTool,
)

# 關鍵字路由（LLM fallback 前的快速路由）
_ORDER_PATTERN = re.compile(r"訂單|order|ORD-|ord-|物流|配送|送達|到哪")
_PRODUCT_PATTERN = re.compile(r"商品|產品|product|搜尋|推薦|電子")
_TICKET_PATTERN = re.compile(r"投訴|客訴|抱怨|工單|ticket|申訴")

ROUTER_SYSTEM_PROMPT = (
    "你是一個客服意圖分類器。根據用戶訊息，判斷應該使用哪個工具。\n"
    '回傳 JSON 格式：{"tool": "<tool_name>", "reasoning": "<原因>"}\n\n'
    "可用工具：\n"
    "- order_lookup: 查詢訂單狀態（含訂單號、物流、配送）\n"
    "- product_search: 搜尋商品（含產品推薦、商品查詢）\n"
    "- ticket_creation: 建立客服工單（含投訴、申訴、問題回報）\n"
    "- rag_query: 查詢知識庫（退貨政策、使用說明等知識型問題）\n"
    "- direct: 直接回答（簡單寒暄、無需工具）"
)

RESPOND_SYSTEM_PROMPT = (
    "你是一個專業的電商客服助手。"
    "根據工具返回的結果，用友善的語氣回答用戶的問題。"
    "請確保回答準確、完整且有幫助。"
)

_VALID_TOOLS = {
    "order_lookup",
    "product_search",
    "ticket_creation",
    "rag_query",
}


class AgentState(TypedDict):
    messages: list[dict[str, str]]
    user_message: str
    tenant_id: str
    kb_id: str
    kb_ids: list[str]
    system_prompt: str
    llm_params: dict[str, Any]
    current_tool: str
    tool_reasoning: str
    tool_result: dict[str, Any]
    final_answer: str
    accumulated_usage: dict[str, Any]


def _keyword_route(msg: str) -> dict[str, str] | None:  # noqa: C901
    """快速關鍵字路由"""
    if _ORDER_PATTERN.search(msg):
        return {
            "current_tool": "order_lookup",
            "tool_reasoning": "用戶查詢訂單狀態",
        }
    if _TICKET_PATTERN.search(msg):
        return {
            "current_tool": "ticket_creation",
            "tool_reasoning": "用戶需要建立客服工單",
        }
    if _PRODUCT_PATTERN.search(msg):
        return {
            "current_tool": "product_search",
            "tool_reasoning": "用戶搜尋商品",
        }
    return None


def _extract_llm_kwargs(state: AgentState) -> dict[str, Any]:
    """從 state.llm_params 取出 LLMService.generate() 接受的 kwargs"""
    params = state.get("llm_params") or {}
    kwargs: dict[str, Any] = {}
    if "temperature" in params:
        kwargs["temperature"] = params["temperature"]
    if "max_tokens" in params:
        kwargs["max_tokens"] = params["max_tokens"]
    if "frequency_penalty" in params:
        kwargs["frequency_penalty"] = params["frequency_penalty"]
    return kwargs


def build_agent_graph(  # noqa: C901
    llm_service: LLMService,
    rag_tool: RAGQueryTool,
    order_tool: OrderLookupTool,
    product_tool: ProductSearchTool,
    ticket_tool: TicketCreationTool,
) -> StateGraph:
    """建構 Agent StateGraph"""

    def _usage_to_dict(usage: Any) -> dict[str, Any]:
        return {
            "model": usage.model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "estimated_cost": usage.estimated_cost,
        }

    def _merge_usage(
        existing: dict[str, Any] | None, new_dict: dict[str, Any]
    ) -> dict[str, Any]:
        if not existing:
            return new_dict
        return {
            "model": existing.get("model", new_dict["model"]),
            "input_tokens": existing.get("input_tokens", 0)
            + new_dict["input_tokens"],
            "output_tokens": existing.get("output_tokens", 0)
            + new_dict["output_tokens"],
            "total_tokens": existing.get("total_tokens", 0)
            + new_dict["total_tokens"],
            "estimated_cost": existing.get("estimated_cost", 0.0)
            + new_dict["estimated_cost"],
        }

    async def router_node(state: AgentState) -> dict:
        """路由：判斷用戶意圖"""
        msg = state["user_message"]
        kw_result = _keyword_route(msg)
        if kw_result:
            return kw_result

        # LLM 意圖分類
        llm_kw = _extract_llm_kwargs(state)
        try:
            result = await llm_service.generate(
                ROUTER_SYSTEM_PROMPT, msg, "", **llm_kw
            )
            usage_dict = _usage_to_dict(result.usage)
            accumulated = _merge_usage(
                state.get("accumulated_usage"), usage_dict
            )
            parsed = json.loads(result.text)
            tool = parsed.get("tool", "rag_query")
            reasoning = parsed.get("reasoning", "LLM 意圖分類")
            return {
                "current_tool": tool,
                "tool_reasoning": reasoning,
                "accumulated_usage": accumulated,
            }
        except (json.JSONDecodeError, KeyError):
            return {
                "current_tool": "rag_query",
                "tool_reasoning": "預設走知識庫查詢",
            }

    async def rag_tool_node(state: AgentState) -> dict:
        kb_ids = state.get("kb_ids") or []
        if not kb_ids and state.get("kb_id"):
            kb_ids = [state["kb_id"]]
        result = await rag_tool.invoke(
            state["tenant_id"],
            kb_ids[0] if kb_ids else state.get("kb_id", ""),
            state["user_message"],
            kb_ids=kb_ids if len(kb_ids) > 1 else None,
        )
        return {"tool_result": result}

    async def order_tool_node(state: AgentState) -> dict:
        order_match = re.search(
            r"[Oo][Rr][Dd]-?\d+", state["user_message"]
        )
        order_id = (
            order_match.group(0) if order_match else "unknown"
        )
        result = await order_tool.invoke(order_id)
        return {"tool_result": result}

    async def product_tool_node(state: AgentState) -> dict:
        result = await product_tool.invoke(state["user_message"])
        return {"tool_result": result}

    async def ticket_tool_node(state: AgentState) -> dict:
        result = await ticket_tool.invoke(
            tenant_id=state["tenant_id"],
            subject="客戶投訴",
            description=state["user_message"],
        )
        return {"tool_result": result}

    async def respond_node(state: AgentState) -> dict:
        """根據工具結果生成最終回答"""
        tool_result = state.get("tool_result", {})
        context = json.dumps(
            tool_result, ensure_ascii=False, default=str
        )
        custom_prompt = state.get("system_prompt") or ""
        sys_prompt = custom_prompt if custom_prompt.strip() else RESPOND_SYSTEM_PROMPT
        llm_kw = _extract_llm_kwargs(state)
        result = await llm_service.generate(
            sys_prompt, state["user_message"], context, **llm_kw
        )
        usage_dict = _usage_to_dict(result.usage)
        accumulated = _merge_usage(
            state.get("accumulated_usage"), usage_dict
        )
        return {
            "final_answer": result.text,
            "accumulated_usage": accumulated,
        }

    def route_to_tool(state: AgentState) -> str:
        tool = state.get("current_tool", "rag_query")
        if tool in _VALID_TOOLS:
            return tool
        return "direct"

    # Build graph
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("rag_tool", rag_tool_node)
    graph.add_node("order_tool", order_tool_node)
    graph.add_node("product_tool", product_tool_node)
    graph.add_node("ticket_tool", ticket_tool_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        route_to_tool,
        {
            "rag_query": "rag_tool",
            "order_lookup": "order_tool",
            "product_search": "product_tool",
            "ticket_creation": "ticket_tool",
            "direct": "respond",
        },
    )

    graph.add_edge("rag_tool", "respond")
    graph.add_edge("order_tool", "respond")
    graph.add_edge("product_tool", "respond")
    graph.add_edge("ticket_tool", "respond")
    graph.add_edge("respond", END)

    return graph
