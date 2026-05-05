"""arq Worker — 背景任務處理

啟動方式：
    uv run arq src.worker.WorkerSettings

Tasks:
    - process_document: PDF OCR + chunking + embedding
    - extract_memory: 記憶萃取
    - run_evaluation: RAG 品質評估
"""

import logging

from arq import cron, func
from arq.connections import RedisSettings

from src.config import Settings

logger = logging.getLogger("arq.worker")


async def startup(ctx: dict) -> None:
    """Worker 啟動時驗證 settings。"""
    logger.info("[worker] ready")


def _new_container():
    """每個 job 建全新 Container — 避免 session/repo 共用衝突。"""
    from src.container import Container
    return Container()


async def shutdown(ctx: dict) -> None:
    logger.info("[worker] shutting down")


# --- Task: split_pdf ---

async def split_pdf_task(ctx: dict, document_id: str, task_id: str) -> None:
    """拆 PDF 為每頁 PNG，並行 enqueue OCR jobs。"""
    logger.info(f"[split_pdf] start doc={document_id} task={task_id}")
    container = _new_container()
    use_case = container.split_pdf_use_case()
    await use_case.execute(document_id, task_id)
    logger.info(f"[split_pdf] done doc={document_id}")


# --- Task: process_document ---

async def process_document_task(ctx: dict, document_id: str, task_id: str) -> None:
    """處理文件：parse + chunk + embed + store to vector DB."""
    logger.info(f"[process_document] start doc={document_id} task={task_id}")
    container = _new_container()
    use_case = container.process_document_use_case()
    await use_case.execute(document_id, task_id)
    logger.info(f"[process_document] done doc={document_id}")


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
    logger.info(f"[extract_memory] start profile={profile_id}")
    from src.application.memory.extract_memory_use_case import ExtractMemoryCommand

    container = _new_container()
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


# --- Task: classify_kb ---

async def classify_kb_task(ctx: dict, kb_id: str, tenant_id: str) -> None:
    """知識庫自動分類：向量聚類 + LLM 命名。"""
    logger.info(f"[classify_kb] start kb={kb_id}")
    container = _new_container()
    use_case = container.classify_kb_use_case()
    await use_case.execute(kb_id, tenant_id)
    logger.info(f"[classify_kb] done kb={kb_id}")


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
    logger.info(f"[run_evaluation] start trace={trace_id} depth={eval_depth}")
    container = _new_container()
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


# --- Cron Task: monthly_reset (S-Token-Gov.2) ---

async def monthly_reset_task(ctx: dict) -> None:
    """每月 1 日為所有租戶建本月新 ledger，addon 從上月 carryover。

    Cron 排程：UTC 每月 1 日 00:05 = Asia/Taipei 每月 1 日 08:05；
    冪等：若本月 ledger 已建（如使用者月初活動先觸發 EnsureLedger），跳過。
    """
    logger.info("[monthly_reset] start")
    container = _new_container()
    use_case = container.process_monthly_reset_use_case()
    stats = await use_case.execute()
    logger.info(
        f"[monthly_reset] done cycle={stats['cycle']} "
        f"processed={stats['processed']} created={stats['created']} "
        f"skipped={stats['skipped']} failed={stats['failed']}"
    )


# --- Cron Task: quota_alerts (S-Token-Gov.3) ---

async def quota_alerts_task(ctx: dict) -> None:
    """每天掃所有租戶本月 ledger，達 80% / 100% 寫 alert log。

    Cron 排程：UTC 每天 01:00 = Asia/Taipei 09:00（避開月度重置 00:05）。
    冪等：QuotaAlertLogRepository.save_if_new 利用 DB UNIQUE 擋重複。
    """
    logger.info("[quota_alerts] start")
    container = _new_container()
    use_case = container.process_quota_alerts_use_case()
    stats = await use_case.execute()
    logger.info(
        f"[quota_alerts] done checked={stats['checked']} "
        f"warnings={stats['warnings']} exhausted={stats['exhausted']}"
    )


# --- Cron Task: quota_email_dispatch (S-Token-Gov.3.5) ---

async def quota_email_dispatch_task(ctx: dict) -> None:
    """每天掃 quota_alert_logs.delivered_to_email=False，呼叫 SendGrid 寄出。

    Cron 排程：UTC 每天 01:30 = Asia/Taipei 09:30（等 quota_alerts_task 跑完）。
    冪等：mark_delivered 後下次 find_undelivered 不會回該筆。
    """
    logger.info("[quota_email_dispatch] start")
    container = _new_container()
    use_case = container.quota_email_dispatch_use_case()
    stats = await use_case.execute()
    logger.info(
        f"[quota_email_dispatch] done scanned={stats['scanned']} "
        f"sent={stats['sent']} skipped_no_email={stats['skipped_no_email']} "
        f"failed={stats['failed']}"
    )


# --- Cron + Job: conversation_summary (S-Gov.6b) ---

async def reembed_chunk_task(ctx: dict, chunk_id: str) -> None:
    """S-KB-Studio.1: 單 chunk 重新向量化（chunk content 改動後觸發）。"""
    logger.info(f"[reembed_chunk] start chunk={chunk_id}")
    from src.application.knowledge.reembed_chunk_use_case import (
        ReEmbedChunkCommand,
    )
    container = _new_container()
    use_case = container.reembed_chunk_use_case()
    await use_case.execute(ReEmbedChunkCommand(chunk_id=chunk_id))
    logger.info(f"[reembed_chunk] done chunk={chunk_id}")


async def conversation_summary_scan_task(ctx: dict) -> None:
    """每分鐘掃 conversations 找需要生 summary 的，個別 enqueue arq job。

    避免單一 cron 跑 100 個 LLM 呼叫卡住下次 cron — 拆 fan-out。
    """
    container = _new_container()
    conv_repo = container.conversation_repository()
    pending = await conv_repo.find_pending_summary(idle_minutes=5, limit=200)
    if not pending:
        return
    logger.info(f"[conv_summary_scan] enqueue {len(pending)} jobs")
    redis = ctx["redis"]
    for conv_id in pending:
        await redis.enqueue_job("process_conversation_summary", conv_id)


async def process_conversation_summary_task(
    ctx: dict, conversation_id: str,
) -> None:
    """單 conversation 生 summary + embed + Milvus upsert + 兩次 record_usage。"""
    logger.info(f"[conv_summary] start conv={conversation_id}")
    container = _new_container()
    use_case = container.generate_conversation_summary_use_case()
    result = await use_case.execute(conversation_id)
    logger.info(f"[conv_summary] done conv={conversation_id} {result}")


async def drain_outbox_task(ctx: dict) -> None:
    """Outbox Pattern Phase A — 每分鐘 cron tick 撈 batch 對外部系統套用。

    Phase A 期間沒有業務 use case 寫入 outbox，drain 永遠空轉（safe）。
    Phase B-D 開始有 vector.delete / vector.drop_collection 事件流入。
    """
    container = _new_container()
    use_case = container.drain_outbox_use_case()
    result = await use_case.execute()
    if result.claimed > 0:
        logger.info(
            f"[drain_outbox] claimed={result.claimed} "
            f"succeeded={result.succeeded} failed={result.failed} "
            f"skipped={result.skipped_no_handler}"
        )


class WorkerSettings:
    """arq worker configuration."""

    functions = [
        func(split_pdf_task, name="split_pdf"),
        func(process_document_task, name="process_document"),
        func(extract_memory_task, name="extract_memory"),
        func(run_evaluation_task, name="run_evaluation"),
        func(classify_kb_task, name="classify_kb"),
        # S-Gov.6b: 對話 summary 個別 job（cron fan-out）
        func(
            process_conversation_summary_task,
            name="process_conversation_summary",
        ),
        # S-KB-Studio.1: 單 chunk re-embed
        func(reembed_chunk_task, name="reembed_chunk"),
        # Outbox Pattern Phase A — drain 用 cron 觸發
        func(drain_outbox_task, name="drain_outbox"),
    ]
    # S-Token-Gov.2: 月度重置（每月 1 日 00:05 UTC = 08:05 Asia/Taipei）
    # S-Token-Gov.3: 額度警示（每天 01:00 UTC = 09:00 Asia/Taipei）
    # S-Token-Gov.3.5: 警示 email 寄送（每天 01:30 UTC = 09:30 Asia/Taipei）
    # S-Gov.6b: 對話摘要掃 pending（每分鐘 — 5min 閒置即生）
    # Outbox: 每分鐘 drain（events 為 DELETE 類，少量；batch_size=50 撐得起）
    cron_jobs = [
        cron(monthly_reset_task, hour={0}, minute={5}, day={1}),
        cron(quota_alerts_task, hour={1}, minute={0}),
        cron(quota_email_dispatch_task, hour={1}, minute={30}),
        cron(conversation_summary_scan_task, minute=set(range(60))),
        cron(drain_outbox_task, minute=set(range(60))),
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
