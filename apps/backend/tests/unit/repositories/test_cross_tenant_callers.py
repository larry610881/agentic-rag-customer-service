"""跨租戶呼叫端 regression（Issue #101 B8：repository tenant fence 追出的缺口）。

repository 以 id 查詢、不帶 tenant 條件的方法，歸屬檢查必須由呼叫端做。
test_repository_tenant_filter_fence.py 逐一追呼叫端時，以下路徑沒有檢查：

- document_router 整支（列表、子頁、檢視原檔、預覽網址、chunks、刪除、批次刪除、
  重處理、批次重處理、confirm-upload）只驗登入、不驗 KB / 文件歸屬
- KB Playground 帶他租戶 bot_id → 他租戶 bot 提示詞進改寫 context
- 優化成本估算帶他租戶 dataset / bot → 回題數與提示詞 token 數
- re-embed chunk 端點註解說 worker 會驗歸屬，實際 worker 不知道呼叫者租戶
- 對話鎖拒絕時的忙碌訊息讀他租戶 bot 設定
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.bot.entity import Bot
from src.domain.eval_dataset.entity import EvalDataset
from src.domain.knowledge.entity import (
    Chunk,
    Document,
    KnowledgeBase,
    ProcessingTask,
)
from src.domain.knowledge.value_objects import DocumentId, KnowledgeBaseId
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError

OWNER = "tenant-owner"
ATTACKER = "tenant-attacker"


def _kb_repo(kb_id: str = "kb-1", tenant_id: str = OWNER) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = KnowledgeBase(
        id=KnowledgeBaseId(value=kb_id), tenant_id=tenant_id, name="kb"
    )
    return repo


def _doc_repo(doc_id: str = "doc-1", kb_id: str = "kb-1") -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = Document(
        id=DocumentId(value=doc_id), kb_id=kb_id, tenant_id=OWNER
    )
    return repo


# ---------------------------------------------------------------- document_router


def _scope(kb_id: str, tenant_id: str, doc_id: str | None, kb_repo, doc_repo):
    from src.interfaces.api.document_router import require_kb_document_scope

    params = {"kb_id": kb_id} | ({"doc_id": doc_id} if doc_id else {})
    return asyncio.run(
        require_kb_document_scope(
            request=SimpleNamespace(path_params=params),
            kb_id=kb_id,
            tenant=CurrentTenant(tenant_id=tenant_id),
            kb_repo=kb_repo,
            doc_repo=doc_repo,
        )
    )


def test_document_router_rejects_other_tenants_kb():
    with pytest.raises(ApiError) as exc:
        _scope("kb-1", ATTACKER, None, _kb_repo(), _doc_repo())
    assert exc.value.status_code == 404


def test_document_router_rejects_doc_outside_path_kb():
    """攻擊者用自己的 KB 路徑，帶他租戶文件 id（view / preview-url / delete…）。"""
    kb_repo = _kb_repo("kb-mine", ATTACKER)
    doc_repo = _doc_repo("doc-victim", "kb-victim")
    with pytest.raises(ApiError) as exc:
        _scope("kb-mine", ATTACKER, "doc-victim", kb_repo, doc_repo)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Document 'doc-victim' not found"


def test_document_router_allows_owner_and_system_admin():
    assert _scope("kb-1", OWNER, "doc-1", _kb_repo(), _doc_repo()) is None
    assert _scope("kb-1", SYSTEM_TENANT_ID, "doc-1", _kb_repo(), _doc_repo()) is None


def test_every_document_route_carries_the_scope_dependency():
    from src.interfaces.api.document_router import (
        require_kb_document_scope,
        router,
    )

    for route in router.routes:
        deps = [d.call for d in route.dependant.dependencies]
        assert require_kb_document_scope in deps, route.path


def test_delete_document_refuses_doc_from_another_kb():
    from src.application.knowledge.delete_document_use_case import (
        DeleteDocumentUseCase,
    )

    doc_repo = _doc_repo("doc-victim", "kb-victim")
    uc = DeleteDocumentUseCase(doc_repo, AsyncMock(), AsyncMock())
    with pytest.raises(EntityNotFoundError):
        asyncio.run(uc.execute("doc-victim", kb_id="kb-mine"))
    doc_repo.delete.assert_not_awaited()
    doc_repo.find_children.assert_not_awaited()


def test_begin_reprocess_refuses_doc_from_another_kb():
    from src.application.knowledge.reprocess_document_use_case import (
        ReprocessDocumentUseCase,
    )

    uc = ReprocessDocumentUseCase.__new__(ReprocessDocumentUseCase)
    uc._doc_repo = _doc_repo("doc-victim", "kb-victim")
    uc._task_repo = AsyncMock()
    with pytest.raises(EntityNotFoundError):
        asyncio.run(uc.begin_reprocess("doc-victim", ATTACKER, kb_id="kb-mine"))
    uc._task_repo.save.assert_not_awaited()
    uc._doc_repo.update_status.assert_not_awaited()


def test_confirm_upload_refuses_doc_or_task_outside_kb():
    from src.application.knowledge.upload_document_use_case import (
        UploadDocumentUseCase,
    )

    uc = UploadDocumentUseCase.__new__(UploadDocumentUseCase)
    uc._doc_repo = _doc_repo("doc-victim", "kb-victim")
    uc._task_repo = AsyncMock()
    uc._task_repo.find_by_id.return_value = ProcessingTask(document_id="doc-victim")
    with pytest.raises(EntityNotFoundError):
        asyncio.run(uc.confirm_upload("doc-victim", "task-1", kb_id="kb-mine"))

    # 文件屬於路徑 KB，但 task 是別份文件的 → 也拒絕
    uc._doc_repo = _doc_repo("doc-1", "kb-mine")
    with pytest.raises(EntityNotFoundError):
        asyncio.run(uc.confirm_upload("doc-1", "task-1", kb_id="kb-mine"))


# ---------------------------------------------------------------- playground


class _StopAfterCommand(Exception):
    pass


def _playground_prompt(bot_tenant: str, requester: str) -> str:
    from src.application.knowledge.test_retrieval_use_case import (
        TestRetrievalCommand,
        TestRetrievalUseCase,
    )

    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = Bot(
        tenant_id=bot_tenant, bot_prompt="SECRET PERSONA"
    )
    query_rag = AsyncMock()
    captured: dict = {}

    async def _retrieve(cmd):
        captured["cmd"] = cmd
        raise _StopAfterCommand

    query_rag.retrieve.side_effect = _retrieve
    uc = TestRetrievalUseCase(
        kb_repo=_kb_repo("kb-1", requester),
        embedding_service=AsyncMock(),
        vector_store=AsyncMock(),
        bot_repository=bot_repo,
        query_rag_use_case=query_rag,
    )
    with pytest.raises(_StopAfterCommand):
        asyncio.run(
            uc.execute(
                TestRetrievalCommand(
                    kb_id="kb-1", tenant_id=requester, query="q", bot_id="bot-x"
                )
            )
        )
    return captured["cmd"].bot_system_prompt


def test_playground_does_not_load_other_tenants_bot_prompt():
    assert _playground_prompt(bot_tenant=OWNER, requester=ATTACKER) == ""


def test_playground_loads_own_bot_prompt():
    assert _playground_prompt(bot_tenant=OWNER, requester=OWNER) == "SECRET PERSONA"


# ---------------------------------------------------------------- cost estimate


def _estimate(dataset_tenant: str, bot_tenant: str, requester: str, role=None):
    from src.application.eval_dataset.eval_use_cases import (
        EstimateCostCommand,
        EstimateCostUseCase,
    )

    ds_repo = AsyncMock()
    ds_repo.find_by_id.return_value = EvalDataset(tenant_id=dataset_tenant)
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = Bot(tenant_id=bot_tenant, bot_prompt="x")
    uc = EstimateCostUseCase(ds_repo, bot_repository=bot_repo)
    return asyncio.run(
        uc.execute(
            EstimateCostCommand(
                dataset_id="ds-1",
                bot_id="bot-1",
                model_id="m",
                tenant_id=requester,
                role=role,
            )
        )
    )


def test_estimate_cost_refuses_other_tenants_dataset():
    with pytest.raises(EntityNotFoundError):
        _estimate(dataset_tenant=OWNER, bot_tenant=ATTACKER, requester=ATTACKER)


def test_estimate_cost_refuses_other_tenants_bot():
    with pytest.raises(EntityNotFoundError) as exc:
        _estimate(dataset_tenant=ATTACKER, bot_tenant=OWNER, requester=ATTACKER)
    assert exc.value.entity_type == "Bot"


def test_estimate_cost_allows_owner_and_system_admin():
    assert _estimate(OWNER, OWNER, OWNER)["num_cases"] == 0
    assert _estimate(OWNER, OWNER, ATTACKER, role="system_admin")["num_cases"] == 0


# ---------------------------------------------------------------- re-embed


def test_re_embed_refuses_other_tenants_chunk():
    from src.interfaces.api.admin_chunk_router import re_embed_chunk

    doc_repo = AsyncMock()
    doc_repo.find_chunk_by_id.return_value = Chunk(tenant_id=OWNER)
    with patch(
        "src.infrastructure.queue.arq_pool.enqueue", new=AsyncMock()
    ) as enqueue:
        with pytest.raises(ApiError) as exc:
            asyncio.run(
                re_embed_chunk(
                    chunk_id="c-1",
                    tenant=CurrentTenant(tenant_id=ATTACKER),
                    doc_repo=doc_repo,
                )
            )
        assert exc.value.status_code == 404
        enqueue.assert_not_awaited()

        asyncio.run(
            re_embed_chunk(
                chunk_id="c-1",
                tenant=CurrentTenant(tenant_id=OWNER),
                doc_repo=doc_repo,
            )
        )
        enqueue.assert_awaited_once_with("reembed_chunk", "c-1")


# ---------------------------------------------------------------- busy reply


def test_busy_reply_ignores_other_tenants_bot():
    from src.application.agent.send_message_use_case import SendMessageUseCase

    uc = SendMessageUseCase.__new__(SendMessageUseCase)
    uc._bot_repo = AsyncMock()
    uc._bot_repo.find_by_id.return_value = Bot(
        tenant_id=OWNER, busy_reply_message="owner-only text"
    )
    cmd = SimpleNamespace(bot_id="bot-1", tenant_id=ATTACKER)
    assert asyncio.run(uc._get_busy_reply_message(cmd)) != "owner-only text"
    cmd = SimpleNamespace(bot_id="bot-1", tenant_id=OWNER)
    assert asyncio.run(uc._get_busy_reply_message(cmd)) == "owner-only text"
