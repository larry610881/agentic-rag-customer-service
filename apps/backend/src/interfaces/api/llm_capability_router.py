"""LLM 結構化輸出能力查詢（Issue #70）

前端 bot 設定表單選 output_format=json 時，依供應商 / 模型顯示 A / B / C 級提示：
- native_schema：API 原生 JSON schema
- json_object：只能要求 JSON 物件，schema 進 prompt、系統驗證
- prompt_only：純 prompt 約束 + 系統驗證
能力表維護於 ``src/domain/llm/structured_output.py``。
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.domain.llm.structured_output import capability
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


class StructuredOutputCapabilityResponse(BaseModel):
    provider: str
    model: str
    tier: str  # native_schema | json_object | prompt_only
    note: str


@router.get(
    "/structured-output-capability",
    response_model=StructuredOutputCapabilityResponse,
)
async def get_structured_output_capability(
    provider: str = Query("", max_length=50),
    model: str = Query("", max_length=100),
    _tenant: CurrentTenant = Depends(get_current_tenant),
) -> StructuredOutputCapabilityResponse:
    tier, note = capability(provider, model)
    return StructuredOutputCapabilityResponse(
        provider=provider, model=model, tier=tier, note=note,
    )
