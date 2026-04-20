# HARDCODE - 地端模型 A/B 測試用路由，正式上線前移除整個檔案
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

import httpx
from src.config import Settings

router = APIRouter(prefix="/ollama", tags=["ollama-test"])

# HARDCODE - A/B 測試預設模型，正式上線前移除
_AB_PRESETS = [
    {"label": "A", "model": "qwen3.6:14b",  "description": "Qwen 3.6 14B"},
    {"label": "B", "model": "qwen3.5:27b",  "description": "Qwen 3.5 27B"},
]


class ModelStatusResponse(BaseModel):
    model: str
    status: str   # "ready" | "not_loaded" | "unreachable"


class AbPreset(BaseModel):
    label: str
    model: str
    description: str


@router.get("/ab-presets", response_model=list[AbPreset])
async def get_ab_presets() -> list[AbPreset]:
    """HARDCODE - 回傳 A/B 測試的模型選項清單。正式上線前移除。"""
    return [AbPreset(**p) for p in _AB_PRESETS]


@router.get("/model-status", response_model=ModelStatusResponse)
async def get_model_status(model: str) -> ModelStatusResponse:
    """查詢指定模型是否已載入 Ollama VRAM（透過 /api/ps）。"""
    cfg = Settings()
    base_url = cfg.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/api/ps")
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        return ModelStatusResponse(model=model, status="unreachable")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="無法連線至 Ollama 服務",
        )

    running: list[str] = [m.get("name", "") for m in data.get("models", [])]
    loaded = any(r == model or r.startswith(f"{model}:") for r in running)
    return ModelStatusResponse(
        model=model,
        status="ready" if loaded else "not_loaded",
    )
