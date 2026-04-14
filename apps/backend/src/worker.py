"""arq Worker — 背景任務處理

啟動方式：
    uv run arq src.worker.WorkerSettings

Tasks:
    - process_document: PDF OCR + chunking + embedding
    - extract_memory: 記憶萃取
    - run_evaluation: RAG 品質評估
"""

import logging

from arq import func
from arq.connections import RedisSettings

from src.config import Settings

logger = logging.getLogger("arq.worker")


async def startup(ctx: dict) -> None:
    """Worker 啟動時初始化 DI Container。"""
    from src.container import Container

    logger.info("[worker] initializing container...")
    container = Container()
    ctx["container"] = container
    logger.info("[worker] container ready")


async def shutdown(ctx: dict) -> None:
    logger.info("[worker] shutting down")


# --- Task: process_document ---

async def process_document_task(ctx: dict, document_id: str, task_id: str) -> None:
    """處理文件：parse + chunk + embed + store to vector DB."""
    from src.infrastructure.db.engine import async_session_factory
    from src.infrastructure.db.session_middleware import _request_session

    logger.info(f"[process_document] start doc={document_id} task={task_id}")
    # Each job gets a fresh session — prevents concurrent session conflicts
    session = async_session_factory()
    token = _request_session.set(session)
    try:
        container = ctx["container"]
        use_case = container.process_document_use_case()
        await use_case.execute(document_id, task_id)
        logger.info(f"[process_document] done doc={document_id}")
    finally:
        _request_session.reset(token)
        if session.in_transaction():
            await session.rollback()
        await session.close()


# --- Task: extract_memory ---

async def extract_memory_task(
    ctx: dict,
    profile_id: str,
    tenant_id: str,
    conversation_id: str,
    messages: list[dict],
    extraction_prompt: str,
) -> None:
    """記憶萃取：從對話中提取使用者記憶事實。"""
    from src.infrastructure.db.engine import async_session_factory
    from src.infrastructure.db.session_middleware import _request_session

    logger.info(f"[extract_memory] start profile={profile_id}")
    from src.application.memory.extract_memory_use_case import ExtractMemoryCommand

    session = async_session_factory()
    token = _request_session.set(session)
    try:
        container = ctx["container"]
        use_case = container.extract_memory_use_case()
        await use_case.execute(
            ExtractMemoryCommand(
                profile_id=profile_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                messages=messages,
                extraction_prompt=extraction_prompt,
            )
        )
        logger.info(f"[extract_memory] done profile={profile_id}")
    finally:
        _request_session.reset(token)
        if session.in_transaction():
            await session.rollback()
        await session.close()


# --- Task: run_evaluation ---

async def run_evaluation_task(
    ctx: dict,
    eval_depth: str,
    query: str,
    answer: str,
    sources: list,
    tool_calls: list,
    tenant_id: str,
    trace_id: str,
    eval_provider: str,
    eval_model: str,
) -> None:
    """RAG 品質評估：L1 檢索 + L2 回答 + L3 Agent。"""
    from src.infrastructure.db.engine import async_session_factory
    from src.infrastructure.db.session_middleware import _request_session

    logger.info(f"[run_evaluation] start trace={trace_id} depth={eval_depth}")
    session = async_session_factory()
    token = _request_session.set(session)
    try:
        container = ctx["container"]
        eval_use_case = container.rag_evaluation_use_case()

        eval_llm = container.llm_service()
        if eval_provider or eval_model:
            if hasattr(eval_llm, "resolve_for_bot"):
                eval_llm = await eval_llm.resolve_for_bot(
                    provider_name=eval_provider,
                    model=eval_model,
                )

        context_texts = [s.get("content_snippet", "") for s in sources if isinstance(s, dict)]

        await eval_use_case.evaluate_combined(
            query=query,
            answer=answer,
            context_texts=context_texts,
            tool_calls=tool_calls,
            eval_depth=eval_depth,
            tenant_id=tenant_id,
            trace_id=trace_id,
            llm_service_override=eval_llm,
        )
        logger.info(f"[run_evaluation] done trace={trace_id}")
    finally:
        _request_session.reset(token)
        if session.in_transaction():
            await session.rollback()
        await session.close()


class WorkerSettings:
    """arq worker configuration."""

    functions = [
        func(process_document_task, name="process_document"),
        func(extract_memory_task, name="extract_memory"),
        func(run_evaluation_task, name="run_evaluation"),
    ]
    on_startup = startup
    on_shutdown = shutdown
    @staticmethod
    def _parse_redis() -> RedisSettings:
        from urllib.parse import urlparse, unquote
        url = Settings().redis_url
        parsed = urlparse(url)
        return RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=unquote(parsed.password) if parsed.password else None,
            database=int(parsed.path.lstrip("/") or 0),
        )

    redis_settings = _parse_redis()
    max_jobs = 3
    job_timeout = 600  # 10 minutes
    health_check_interval = 30
    log_results = True
