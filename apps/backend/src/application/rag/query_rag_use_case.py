"""RAG 查詢用例"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import EmbeddingService, LLMService, VectorStore
from src.domain.rag.value_objects import RAGResponse, Source
from src.domain.shared.exceptions import EntityNotFoundError, NoRelevantKnowledgeError

RAG_SYSTEM_PROMPT = (
    "你是一個專業的電商客服助手。根據提供的知識庫內容回答使用者的問題。"
    "請確保回答準確、有幫助，並引用知識庫中的相關資訊。"
    "如果知識庫中沒有相關資訊，請誠實告知。"
)


@dataclass(frozen=True)
class QueryRAGCommand:
    tenant_id: str
    kb_id: str
    query: str
    top_k: int = 5
    score_threshold: float = 0.3
    kb_ids: list[str] | None = None


class QueryRAGUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        llm_service: LLMService,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._llm_service = llm_service

    async def execute(self, command: QueryRAGCommand) -> RAGResponse:
        effective_kb_ids = command.kb_ids or [command.kb_id]

        # Validate all KBs exist
        for kid in effective_kb_ids:
            kb = await self._kb_repo.find_by_id(kid)
            if kb is None:
                raise EntityNotFoundError("KnowledgeBase", kid)

        query_vector = await self._embedding_service.embed_query(command.query)

        # Search across all KBs and merge results
        all_results = []
        for kid in effective_kb_ids:
            results = await self._vector_store.search(
                collection=f"kb_{kid}",
                query_vector=query_vector,
                limit=command.top_k,
                score_threshold=command.score_threshold,
                filters={"tenant_id": command.tenant_id},
            )
            all_results.extend(results)

        # Sort by score descending, take top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        results = all_results[: command.top_k]

        if not results:
            raise NoRelevantKnowledgeError(command.query)

        context = "\n---\n".join(
            r.payload["content"] for r in results
        )

        llm_result = await self._llm_service.generate(
            RAG_SYSTEM_PROMPT, command.query, context
        )

        sources = [
            Source(
                document_name=r.payload.get("document_name", ""),
                content_snippet=r.payload["content"][:200],
                score=r.score,
                chunk_id=r.id,
            )
            for r in results
        ]

        return RAGResponse(
            answer=llm_result.text,
            sources=sources,
            query=command.query,
            tenant_id=command.tenant_id,
            knowledge_base_id=effective_kb_ids[0],
            usage=llm_result.usage,
        )

    async def execute_stream(
        self, command: QueryRAGCommand
    ) -> AsyncIterator[dict]:
        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", command.kb_id)

        query_vector = await self._embedding_service.embed_query(command.query)

        results = await self._vector_store.search(
            collection=f"kb_{command.kb_id}",
            query_vector=query_vector,
            limit=command.top_k,
            score_threshold=command.score_threshold,
            filters={"tenant_id": command.tenant_id},
        )

        if not results:
            raise NoRelevantKnowledgeError(command.query)

        context = "\n---\n".join(
            r.payload["content"] for r in results
        )

        async for token in self._llm_service.generate_stream(
            RAG_SYSTEM_PROMPT, command.query, context
        ):
            yield {"type": "token", "content": token}

        sources = [
            Source(
                document_name=r.payload.get("document_name", ""),
                content_snippet=r.payload["content"][:200],
                score=r.score,
                chunk_id=r.id,
            )
            for r in results
        ]
        yield {"type": "sources", "sources": [s.to_dict() for s in sources]}
        yield {"type": "done"}
