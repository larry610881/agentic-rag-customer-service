"""QueryWikiUseCase — Wiki 模式查詢編排（Strategy Pattern）。

職責：
1. 載入 bot 的 WikiGraph
2. 依 navigation_strategy 從 navigators dict 取對應 GraphNavigator
3. 呼叫 navigator.navigate() 取得 list[NavigationResult]
4. 組裝成 RAG-compatible tool response dict（schema 跟 RAGQueryTool 一致）

錯誤處理原則：
- WikiGraph 不存在 / status != ready → 回**可讀錯誤訊息**作為 context
  （讓 LLM 看到後可以告訴使用者「Wiki 尚未準備好」，
  而不是 throw exception 導致 agent 整個掛掉）
- 未知 strategy → 才會 throw ValidationError（config bug，應該 fail fast）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.shared.exceptions import ValidationError
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.navigator import (
    VALID_NAVIGATION_STRATEGIES,
    GraphNavigator,
    NavigationResult,
)
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.value_objects import WikiStatus
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueryWikiCommand:
    tenant_id: str
    bot_id: str
    query: str
    navigation_strategy: str = "keyword_bfs"
    top_n: int = 8


@dataclass
class QueryWikiResult:
    """查詢結果 — 含 nodes 與已組裝好的 tool response dict。"""

    nodes: list[NavigationResult]
    tool_response: dict[str, Any]
    """RAG-compatible schema: {success, context, sources}.

    sources element schema (與 src.domain.rag.value_objects.Source.to_dict 對齊):
        {document_name, content_snippet, score, chunk_id, document_id}
    """


class QueryWikiUseCase:
    def __init__(
        self,
        wiki_graph_repository: WikiGraphRepository,
        navigators: dict[str, GraphNavigator],
    ) -> None:
        self._wiki_repo = wiki_graph_repository
        # Frozen reference to navigators dict — DI Container provides it
        self._navigators = navigators

    async def execute(self, command: QueryWikiCommand) -> QueryWikiResult:
        log = logger.bind(
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            strategy=command.navigation_strategy,
        )

        # 1. Validate strategy
        if command.navigation_strategy not in VALID_NAVIGATION_STRATEGIES:
            raise ValidationError(
                f"Unknown wiki navigation strategy: "
                f"{command.navigation_strategy!r}. "
                f"Valid: {list(VALID_NAVIGATION_STRATEGIES)}"
            )
        navigator = self._navigators.get(command.navigation_strategy)
        if navigator is None:
            raise ValidationError(
                f"Strategy '{command.navigation_strategy}' is registered "
                f"as valid but no navigator instance is provided"
            )

        # 2. Load wiki graph
        graph = await self._wiki_repo.find_by_bot_id(
            command.tenant_id, command.bot_id
        )
        if graph is None:
            log.info("wiki.query.not_compiled")
            return self._readable_error_response(
                "此 Bot 的 Wiki 知識圖譜尚未編譯。請先觸發編譯後再進行查詢。"
            )

        if graph.status not in (
            WikiStatus.READY.value,
            WikiStatus.STALE.value,
        ):
            log.info("wiki.query.not_ready", status=graph.status)
            msg = self._status_to_message(graph.status)
            return self._readable_error_response(msg)

        # 3. Navigate
        results = await navigator.navigate(
            query=command.query,
            wiki_graph=graph,
            top_n=command.top_n,
        )
        log.info(
            "wiki.query.completed",
            result_count=len(results),
            node_count=len(graph.nodes),
        )

        if not results:
            return QueryWikiResult(
                nodes=[],
                tool_response={
                    "success": True,
                    "context": "",
                    "sources": [],
                },
            )

        return QueryWikiResult(
            nodes=results,
            tool_response=self._to_tool_response(results, graph),
        )

    @staticmethod
    def _readable_error_response(message: str) -> QueryWikiResult:
        """Return a graceful tool response that the LLM can relay to the user."""
        return QueryWikiResult(
            nodes=[],
            tool_response={
                "success": True,
                "context": message,
                "sources": [],
            },
        )

    @staticmethod
    def _status_to_message(status: str) -> str:
        if status == WikiStatus.COMPILING.value:
            return "Wiki 知識圖譜編譯中，請稍候再試。"
        if status == WikiStatus.PENDING.value:
            return "Wiki 知識圖譜尚未開始編譯。"
        if status == WikiStatus.FAILED.value:
            return "Wiki 知識圖譜編譯失敗，請聯絡管理員。"
        return f"Wiki 知識圖譜目前狀態為 {status}，無法查詢。"

    @staticmethod
    def _to_tool_response(
        results: list[NavigationResult],
        graph: WikiGraph,
    ) -> dict[str, Any]:
        """Convert NavigationResult list into RAG tool schema dict.

        sources element fields:
            document_name → first source_doc_id (or "wiki" placeholder)
            content_snippet → "{label}: {summary}"
            score → navigation result score
            chunk_id → node_id
            document_id → source_doc_id
        """
        context = "\n---\n".join(
            f"{r.label}: {r.summary}" if r.summary else r.label
            for r in results
        )
        sources = [
            {
                "document_name": r.source_doc_id or "wiki",
                "content_snippet": (
                    f"{r.label}: {r.summary}" if r.summary else r.label
                ),
                "score": r.score,
                "chunk_id": r.node_id,
                "document_id": r.source_doc_id or "",
            }
            for r in results
        ]
        return {
            "success": True,
            "context": context,
            "sources": sources,
        }
