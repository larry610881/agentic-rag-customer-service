"""文件管線（process / reprocess）共用的 OCR 引擎選擇與影像 OCR（Issue #78）。

- :func:`select_ocr_engine`：依 ``覆寫 → KB.ocr_model → 租戶 default_ocr_model →
  環境預設`` 決定 spec，向 :class:`OcrEngineSelector`（file parser）取引擎。
  file parser 未實作 port（舊式注入 / 測試替身）時退回其 ``_ocr`` 預設引擎。
- :func:`ocr_image`：單張影像（PDF 子頁 image/png）的 OCR，含 auto 模式的
  page-type dispatch 與 ``ocr_slice_grid`` 切片；過去 process / reprocess 各有一份。
  切片時預設走混合模式（Issue #82）：另跑一次不帶切片前綴的整頁 OCR，由
  helper 以商品名合併補回橫跨切片邊界被省略的 block（``OCR_HYBRID_FULL_PAGE``）。

用量一律累加到 caller 的 :class:`OcrUsageTally`，並行文件之間互不干擾。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.domain.knowledge.services import OcrEngineSelector
from src.domain.knowledge.value_objects import OcrUsageTally

if TYPE_CHECKING:
    from src.domain.knowledge.entity import KnowledgeBase
    from src.domain.tenant.repository import TenantRepository

logger = structlog.get_logger(__name__)


async def _tenant_default_ocr_model(
    tenant_repo: "TenantRepository | None", tenant_id: str
) -> str:
    if tenant_repo is None:
        return ""
    try:
        tenant = await tenant_repo.find_by_id(tenant_id)
    except Exception:
        logger.warning("ocr.tenant_default.lookup_failed", tenant_id=tenant_id)
        return ""
    value = getattr(tenant, "default_ocr_model", "") if tenant else ""
    return value if isinstance(value, str) else ""


async def select_ocr_engine(
    file_parser: Any,
    *,
    kb: "KnowledgeBase | None",
    tenant_repo: "TenantRepository | None",
    tenant_id: str,
    override: str | None = None,
) -> tuple[Any, str]:
    """回傳 ``(engine, spec)``；無可用引擎時 ``(None, "")``。"""
    if not isinstance(file_parser, OcrEngineSelector):
        return getattr(file_parser, "_ocr", None), ""
    kb_spec = override or (getattr(kb, "ocr_model", "") if kb else "") or ""
    tenant_spec = "" if kb_spec else await _tenant_default_ocr_model(
        tenant_repo, tenant_id
    )
    spec = file_parser.resolve_ocr_spec(kb_spec, tenant_spec)
    return file_parser.ocr_engine_for(spec), spec


async def ocr_image(
    engine: Any,
    raw_content: bytes,
    *,
    ocr_mode: str,
    slice_grid: str,
    usage: OcrUsageTally,
) -> str:
    """單張影像 OCR：auto 模式走 page-type dispatch；slice_grid 非空時切片。

    切片 + 結構化 prompt（catalog / auto）時同時提供整頁 callback 給 helper
    做混合補漏；general 模式輸出無 ``===`` block 可合併，不跑整頁。
    """
    from src.infrastructure.file_parser.ocr_engines import prompts as p
    from src.infrastructure.file_parser.sliced_ocr_helper import ocr_image_sliced

    if ocr_mode == "auto" and hasattr(engine, "ocr_page_auto_dispatch"):
        if not slice_grid:
            _page_type, content = await engine.ocr_page_auto_dispatch(
                raw_content, usage=usage
            )
            return str(content)
        # auto + slice：先 classify 整圖拿 page_type，再用對應 prompt 對每個
        # tile OCR（加切片補充規則）。
        page_type = await engine.classify_page_type(raw_content, usage=usage)
        base_prompt = p._PAGE_TYPE_PROMPTS.get(
            page_type, p.OCR_PROMPTS.get("general", "")
        )
        prompt = p._SLICE_AWARE_PREFIX + base_prompt
    else:
        base_prompt = p.OCR_PROMPTS.get(ocr_mode, p.OCR_PROMPTS.get("general", ""))
        # 啟用切片時加切片補充規則 prefix（防「半個商品 → [模糊:???]」）
        prompt = p._SLICE_AWARE_PREFIX + base_prompt if slice_grid else base_prompt

    async def _ocr_tile(tile_bytes: bytes) -> str:
        return str(await engine.ocr_page(tile_bytes, prompt=prompt, usage=usage))

    async def _ocr_full_page(page_bytes: bytes) -> str:
        return str(
            await engine.ocr_page(page_bytes, prompt=base_prompt, usage=usage)
        )

    full_page_callback = (
        _ocr_full_page if slice_grid and ocr_mode != "general" else None
    )
    # ocr_image_sliced grid="" 時直接呼叫 callback 整圖
    return await ocr_image_sliced(
        raw_content, slice_grid, _ocr_tile, full_page_callback=full_page_callback
    )
