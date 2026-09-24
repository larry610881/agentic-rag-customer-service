"""Regression（Issue #65）：delete-by-source 的 vector.delete 事件必須自行 commit。

5e80c3f（Outbox Phase C）改成發 outbox 事件，但只呼叫 save()（不 commit）。
其他刪除 use case 都有後續 atomic() 業務寫入把事件一起 commit；本 use case
不改任何 PG 資料，request 結束時 SessionCleanupMiddleware rollback 把事件丟掉
→ 端點回 204、Milvus 什麼都沒刪。整合測試以另一條連線讀 outbox_events 抓到。
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from src.application.knowledge.delete_documents_by_source_use_case import (
    DeleteDocumentsBySourceCommand,
    DeleteDocumentsBySourceUseCase,
)
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.domain.outbox.repository import OutboxEventRepository


def _kb() -> KnowledgeBase:
    now = datetime.now(timezone.utc)
    return KnowledgeBase(
        id=KnowledgeBaseId(value="kb-1"),
        tenant_id="tenant-001",
        name="kb",
        description="",
        kb_type="user",
        created_at=now,
        updated_at=now,
    )


def test_delete_by_source_事件走自帶_commit_的寫入():
    kb_repo = AsyncMock(spec=KnowledgeBaseRepository)
    kb_repo.find_by_id = AsyncMock(return_value=_kb())
    outbox_repo = AsyncMock(spec=OutboxEventRepository)
    uc = DeleteDocumentsBySourceUseCase(
        kb_repo=kb_repo,
        publish_outbox_event_use_case=PublishOutboxEventUseCase(outbox_repo),
    )

    asyncio.run(
        uc.execute(
            DeleteDocumentsBySourceCommand(
                kb_id="kb-1", tenant_id="tenant-001", source="pmo", source_ids=["a"]
            )
        )
    )

    outbox_repo.save_and_commit.assert_awaited_once()
    outbox_repo.save.assert_not_awaited()
    (event,) = outbox_repo.save_and_commit.await_args.args
    assert event.payload["filters"]["tenant_id"] == "tenant-001"
    assert event.payload["filters"]["source_id"] == ["a"]


def test_publish_預設仍只_save_由呼叫端_atomic_commit():
    outbox_repo = AsyncMock(spec=OutboxEventRepository)
    event = AsyncMock()
    asyncio.run(PublishOutboxEventUseCase(outbox_repo).execute(event))
    outbox_repo.save.assert_awaited_once_with(event)
    outbox_repo.save_and_commit.assert_not_awaited()
