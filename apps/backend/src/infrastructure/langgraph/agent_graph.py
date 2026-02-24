"""LangGraph Agent StateGraph 建構"""

import json
import re
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph

logger = structlog.get_logger(__name__)

from src.domain.rag.services import LLMService
from src.infrastructure.langgraph.tools import (
    OrderLookupTool,
    ProductSearchTool,
    RAGQueryTool,
    TicketCreationTool,
)

# 關鍵字路由（LLM fallback 前的快速路由）
_GREETING_PATTERN = re.compile(
    r"^(你好|哈囉|嗨|hi|hello|hey|早安|午安|晚安|安安|謝謝|感謝|掰掰|再見|bye|thanks|thank you)[哦呀啊喔呢嗎啦耶ㄛㄚ\s!！。？?~～]*$",
    re.IGNORECASE,
)
_ORDER_PATTERN = re.compile(r"訂單|order|ORD-|ord-|物流|配送|送達|到哪")
_PRODUCT_PATTERN = re.compile(r"商品|產品|product|搜尋|推薦|電子")
_TICKET_PATTERN = re.compile(r"投訴|客訴|抱怨|工單|ticket|申訴")

_TOOL_DESCRIPTIONS = {
    "rag_query": "rag_query: 查詢知識庫中的資料（任何可能在知識庫中有答案的問題都應使用此工具）",
    "order_lookup": "order_lookup: 查詢訂單狀態（含訂單號、物流、配送）",
    "product_search": "product_search: 搜尋商品（含產品推薦、商品查詢）",
    "ticket_creation": "ticket_creation: 建立客服工單（含投訴、申訴、問題回報）",
}

_ROUTER_PROMPT_HEADER = (
    "你是一個客服意圖分類器。根據用戶訊息，判斷應該使用哪個工具。\n"
    '回傳 JSON 格式：{"tool": "<tool_name>", "reasoning": "<原因>"}\n\n'
    "可用工具：\n"
)


def _build_router_prompt(enabled_tools: list[str] | None = None) -> str:
    """根據啟用的工具動態產生路由 prompt"""
    tools = enabled_tools if enabled_tools else list(_TOOL_DESCRIPTIONS.keys())
    lines = [f"- {_TOOL_DESCRIPTIONS[t]}" for t in tools if t in _TOOL_DESCRIPTIONS]
    lines.append("- direct: 直接回答（簡單寒暄、無需工具）")
    return _ROUTER_PROMPT_HEADER + "\n".join(lines)


# 預設全工具 prompt（向後相容）
ROUTER_SYSTEM_PROMPT = _build_router_prompt()

RESPOND_SYSTEM_PROMPT = (
    "你是一個專業的電商客服助手，用友善的語氣與用戶對話。\n"
    "如果有提供工具結果，請根據工具結果回答用戶的問題，確保準確、完整。\n"
    "如果沒有工具結果，或工具結果與用戶問題無關，請自然地回應用戶（例如打招呼、閒聊）。\n"
    "不要強行引用不相關的知識庫內容。"
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
    history_context: str
    router_context: str
    current_tool: str
    tool_reasoning: str
    tool_result: dict[str, Any]
    final_answer: str
    accumulated_usage: dict[str, Any]
    enabled_tools: list[str]


def _keyword_route(msg: str) -> dict[str, str] | None:  # noqa: C901
    """快速關鍵字路由"""
    stripped = msg.strip()
    if _GREETING_PATTERN.match(stripped):
        return {
            "current_tool": "direct",
            "tool_reasoning": "簡單寒暄，直接回答",
        }
    if _ORDER_PATTERN.search(stripped):
        return {
            "current_tool": "order_lookup",
            "tool_reasoning": "用戶查詢訂單狀態",
        }
    if _TICKET_PATTERN.search(stripped):
        return {
            "current_tool": "ticket_creation",
            "tool_reasoning": "用戶需要建立客服工單",
        }
    if _PRODUCT_PATTERN.search(stripped):
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
    order_tool: OrderLookupTool | None = None,
    product_tool: ProductSearchTool | None = None,
    ticket_tool: TicketCreationTool | None = None,
    *,
    include_respond: bool = True,
) -> StateGraph:
    """建構 Agent StateGraph

    Args:
        include_respond: True=完整圖(含回答節點), False=僅路由+工具(streaming用)
    """

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
        bot_tools = state.get("enabled_tools") or []

        # 只啟用一個工具 → 跳過路由，直接用那個工具
        if len(bot_tools) == 1:
            tool = bot_tools[0]
            logger.info(
                "agent.router.single_tool",
                message=msg,
                tool=tool,
            )
            return {
                "current_tool": tool,
                "tool_reasoning": f"機器人僅啟用 {tool}",
            }

        kw_result = _keyword_route(msg)
        if kw_result:
            # 關鍵字路由命中的工具必須在啟用清單內
            if bot_tools and kw_result["current_tool"] not in bot_tools and kw_result["current_tool"] != "direct":
                pass  # 不採用，fallthrough 到 LLM 路由
            else:
                logger.info(
                    "agent.router.keyword",
                    message=msg,
                    tool=kw_result["current_tool"],
                    reasoning=kw_result["tool_reasoning"],
                )
                return kw_result

        # LLM 意圖分類（動態 prompt 只列啟用的工具）
        router_prompt = _build_router_prompt(bot_tools if bot_tools else None)
        llm_kw = _extract_llm_kwargs(state)
        router_ctx = state.get("router_context") or ""
        try:
            result = await llm_service.generate(
                router_prompt, msg, router_ctx, **llm_kw
            )
            usage_dict = _usage_to_dict(result.usage)
            accumulated = _merge_usage(
                state.get("accumulated_usage"), usage_dict
            )
            # Strip markdown code block wrapping (e.g. ```json ... ```)
            raw_text = result.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```\w*\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text).strip()
            parsed = json.loads(raw_text)
            tool = parsed.get("tool", "rag_query")
            # 驗證 LLM 選的工具在啟用清單內
            if bot_tools and tool not in bot_tools and tool != "direct":
                tool = bot_tools[0]  # fallback 到第一個啟用的工具
            reasoning = parsed.get("reasoning", "LLM 意圖分類")
            logger.info(
                "agent.router.llm",
                message=msg,
                tool=tool,
                reasoning=reasoning,
                raw_response=result.text[:200],
            )
            return {
                "current_tool": tool,
                "tool_reasoning": reasoning,
                "accumulated_usage": accumulated,
            }
        except (json.JSONDecodeError, KeyError):
            logger.warning(
                "agent.router.fallback.parse",
                message=msg,
                raw_response=result.text[:200] if hasattr(result, "text") else "N/A",
            )
            return {
                "current_tool": "rag_query",
                "tool_reasoning": "預設走知識庫查詢",
            }
        except Exception:
            logger.exception("agent.router.fallback.error", message=msg)
            return {
                "current_tool": "direct",
                "tool_reasoning": "LLM 路由失敗，直接回答",
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
        if not order_tool:
            return {"tool_result": {"error": "order_lookup tool is disabled"}}
        order_match = re.search(
            r"[Oo][Rr][Dd]-?\d+", state["user_message"]
        )
        order_id = (
            order_match.group(0) if order_match else "unknown"
        )
        result = await order_tool.invoke(order_id)
        return {"tool_result": result}

    async def product_tool_node(state: AgentState) -> dict:
        if not product_tool:
            return {"tool_result": {"error": "product_search tool is disabled"}}
        result = await product_tool.invoke(state["user_message"])
        return {"tool_result": result}

    async def ticket_tool_node(state: AgentState) -> dict:
        if not ticket_tool:
            return {"tool_result": {"error": "ticket_creation tool is disabled"}}
        result = await ticket_tool.invoke(
            tenant_id=state["tenant_id"],
            subject="客戶投訴",
            description=state["user_message"],
        )
        return {"tool_result": result}

    async def respond_node(state: AgentState) -> dict:
        """根據工具結果生成最終回答"""
        tool_result = state.get("tool_result", {})
        history_ctx = state.get("history_context") or ""
        parts: list[str] = []
        if history_ctx:
            parts.append(f"[對話歷史]\n{history_ctx}")
        if tool_result:
            tool_json = json.dumps(
                tool_result, ensure_ascii=False, default=str
            )
            parts.append(f"[工具結果]\n{tool_json}")
        context = "\n\n".join(parts)
        custom_prompt = state.get("system_prompt") or ""
        sys_prompt = custom_prompt if custom_prompt.strip() else RESPOND_SYSTEM_PROMPT
        llm_kw = _extract_llm_kwargs(state)
        logger.info(
            "agent.respond.context",
            user_message=state["user_message"],
            tool=state.get("current_tool", ""),
            system_prompt=sys_prompt[:100],
            context=context[:500] if context else "(empty)",
        )
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

    # Build enabled tools set dynamically
    enabled_tools = {"rag_query"}
    if order_tool:
        enabled_tools.add("order_lookup")
    if product_tool:
        enabled_tools.add("product_search")
    if ticket_tool:
        enabled_tools.add("ticket_creation")

    def route_to_tool(state: AgentState) -> str:
        tool = state.get("current_tool", "rag_query")
        if tool in enabled_tools:
            return tool
        return "direct"

    # Build graph
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("rag_tool", rag_tool_node)
    graph.add_node("order_tool", order_tool_node)
    graph.add_node("product_tool", product_tool_node)
    graph.add_node("ticket_tool", ticket_tool_node)

    graph.set_entry_point("router")

    if include_respond:
        graph.add_node("respond", respond_node)
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
    else:
        # Routing + tool only (no respond) — for streaming
        graph.add_conditional_edges(
            "router",
            route_to_tool,
            {
                "rag_query": "rag_tool",
                "order_lookup": "order_tool",
                "product_search": "product_tool",
                "ticket_creation": "ticket_tool",
                "direct": END,
            },
        )
        graph.add_edge("rag_tool", END)
        graph.add_edge("order_tool", END)
        graph.add_edge("product_tool", END)
        graph.add_edge("ticket_tool", END)

    return graph
