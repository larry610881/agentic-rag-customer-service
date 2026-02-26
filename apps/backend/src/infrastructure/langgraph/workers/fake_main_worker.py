"""FakeMainWorker — 從 FakeAgentService 遷移的關鍵字路由邏輯"""

from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult
from src.domain.rag.value_objects import Source, TokenUsage


class FakeMainWorker(AgentWorker):
    """Catch-all Worker：所有問題導向 RAG 知識庫查詢"""

    @property
    def name(self) -> str:
        return "fake_main"

    async def can_handle(self, context: WorkerContext) -> bool:
        return True

    async def handle(self, context: WorkerContext) -> WorkerResult:
        answer = (
            "根據知識庫：本公司提供一年保固服務，"
            "退貨政策為 30 天內可退貨，請保持商品完整。"
        )
        sources = [
            Source(
                document_name="保固政策.txt",
                content_snippet="本公司提供一年保固服務，涵蓋非人為損壞的維修與更換",
                score=0.92,
                chunk_id="chunk-fake-1",
            ),
            Source(
                document_name="退貨政策.txt",
                content_snippet="退貨政策為 30 天內可退貨",
                score=0.9,
                chunk_id="chunk-fake-2",
            ),
        ]

        if context.conversation_history:
            answer = f"根據先前對話，{answer}"

        return WorkerResult(
            answer=answer,
            tool_calls=[
                {"tool_name": "rag_query", "reasoning": "用戶詢問知識型問題"},
            ],
            sources=sources,
            usage=TokenUsage.zero("fake"),
        )
