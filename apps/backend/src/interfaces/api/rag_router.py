"""RAG 查詢 API 端點"""

import json

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError, NoRelevantKnowledgeError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["rag"],
)


class RAGQueryRequest(BaseModel):
    knowledge_base_id: str
    query: str
    top_k: int = 5


class SourceResponse(BaseModel):
    document_name: str
    content_snippet: str
    score: float


class TokenUsageResponse(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    query: str
    usage: TokenUsageResponse | None = None


@router.post("/query", response_model=RAGQueryResponse)
@inject
async def query_rag(
    request: RAGQueryRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: QueryRAGUseCase = Depends(
        Provide[Container.query_rag_use_case]
    ),
    record_usage: RecordUsageUseCase = Depends(
        Provide[Container.record_usage_use_case]
    ),
) -> RAGQueryResponse:
    try:
        result = await use_case.execute(
            QueryRAGCommand(
                tenant_id=tenant.tenant_id,
                kb_id=request.knowledge_base_id,
                query=request.query,
                top_k=request.top_k,
            )
        )
    except NoRelevantKnowledgeError:
        return RAGQueryResponse(
            answer="知識庫中沒有找到相關資訊，請嘗試其他問題。",
            sources=[],
            query=request.query,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None

    await record_usage.execute(
        tenant_id=tenant.tenant_id,
        request_type="rag",
        usage=result.usage,
    )

    usage_resp = None
    if result.usage:
        usage_resp = TokenUsageResponse(
            model=result.usage.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            estimated_cost=result.usage.estimated_cost,
        )

    return RAGQueryResponse(
        answer=result.answer,
        sources=[
            SourceResponse(
                document_name=s.document_name,
                content_snippet=s.content_snippet,
                score=s.score,
            )
            for s in result.sources
        ],
        query=result.query,
        usage=usage_resp,
    )


@router.post("/query/stream")
@inject
async def query_rag_stream(
    request: RAGQueryRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: QueryRAGUseCase = Depends(
        Provide[Container.query_rag_use_case]
    ),
) -> StreamingResponse:
    async def event_generator():
        try:
            async for event in use_case.execute_stream(
                QueryRAGCommand(
                    tenant_id=tenant.tenant_id,
                    kb_id=request.knowledge_base_id,
                    query=request.query,
                    top_k=request.top_k,
                )
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except NoRelevantKnowledgeError:
            no_result = {
                "type": "token",
                "content": "知識庫中沒有找到相關資訊，請嘗試其他問題。",
            }
            yield f"data: {json.dumps(no_result, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except EntityNotFoundError as e:
            error_event = {"type": "error", "message": e.message}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
