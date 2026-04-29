"""PDF 子頁 LLM rename helper（process + reprocess 共用）.

當 PDF 拆頁完成 + chunks 都好了，用 LLM 為每頁生成「第 N 頁 — 主題」標題。
之前只在 process_document 有 → reprocess 子頁時不 rename → drift bug。

模型解析優先序：
  KB.context_model  →  tenant.default_context_model  →  跳過（靜默）
"""

from __future__ import annotations

from src.domain.usage.category import UsageCategory


async def rename_child_page_if_pdf(
    *,
    document_id: str,
    page_number: int,
    content: str,
    kb,
    tenant_id: str,
    doc_repo,
    tenant_repo=None,
    record_usage=None,
    context_service=None,
    log,
) -> None:
    """LLM 生成 PDF 子頁標題寫回 documents.filename。失敗 silent。"""
    if not content or not content.strip():
        return

    # Resolve model: KB.context_model → tenant.default_context_model → 跳過
    model = getattr(kb, "context_model", "") if kb else ""
    if not model and tenant_repo:
        try:
            from sqlalchemy import select

            from src.infrastructure.db.engine import async_session_factory
            from src.infrastructure.db.models.tenant_model import TenantModel
            async with async_session_factory() as session:
                doc = await doc_repo.find_by_id(document_id)
                if doc:
                    stmt = select(TenantModel.default_context_model).where(
                        TenantModel.id == doc.tenant_id
                    )
                    result = await session.execute(stmt)
                    model = result.scalar_one_or_none() or ""
        except Exception:
            pass

    if not model:
        return

    from src.domain.rag.value_objects import TokenUsage
    from src.infrastructure.llm.llm_caller import call_llm

    prompt = f"""\
以下是 PDF 第 {page_number} 頁的 OCR 內容（截取前 2000 字）：

{content[:2000]}

請用 5-15 個繁體中文字總結這頁的主題，作為頁面標題。
格式：「第 N 頁 — 主題」，例如「第 3 頁 — 肉品促銷」。
只輸出標題，不要其他內容。"""

    try:
        result = await call_llm(
            model_spec=model,
            prompt=prompt,
            max_tokens=50,
            api_key_resolver=(
                context_service._api_key_resolver
                if context_service
                and hasattr(context_service, "_api_key_resolver")
                else None
            ),
        )
        new_filename = result.text.strip()[:100]

        # Token-Gov.0: 記錄 PDF 子頁 rename 的 token 用量
        if record_usage and (result.input_tokens + result.output_tokens) > 0:
            kb_id_value = getattr(kb, "id", None)
            # KnowledgeBaseId VO 必須 unwrap 成 str（DB 欄位 VARCHAR）
            if kb_id_value is not None and hasattr(kb_id_value, "value"):
                kb_id_value = kb_id_value.value
            await record_usage.execute(
                tenant_id=tenant_id,
                request_type=UsageCategory.PDF_RENAME.value,
                usage=TokenUsage(
                    model=model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                ),
                kb_id=kb_id_value,
            )

        if new_filename:
            from sqlalchemy import update

            from src.infrastructure.db.engine import async_session_factory
            from src.infrastructure.db.models.document_model import DocumentModel
            async with async_session_factory() as session:
                await session.execute(
                    update(DocumentModel)
                    .where(DocumentModel.id == document_id)
                    .values(filename=new_filename)
                )
                await session.commit()
            log.info(
                "child.renamed",
                document_id=document_id,
                new_name=new_filename,
            )
    except Exception:
        log.warning("child.rename_llm_failed", exc_info=True)
