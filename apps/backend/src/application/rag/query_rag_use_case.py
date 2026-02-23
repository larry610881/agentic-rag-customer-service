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

        answer = await self._llm_service.generate(
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
            answer=answer,
            sources=sources,
            query=command.query,
            tenant_id=command.tenant_id,
            knowledge_base_id=command.kb_id,
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
