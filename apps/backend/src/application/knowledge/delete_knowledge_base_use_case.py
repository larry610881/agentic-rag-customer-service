"""刪除知識庫用例（Phase B — 透過 Outbox Pattern）

修正點：
1. 順序倒轉 — 舊版先 Milvus loop delete 再 PG delete，PG 失敗時 Milvus 已不可逆。
   新版：在 PG cascade delete 同 transaction 內 publish 一筆 vector.drop_collection
   outbox 事件。commit 後 drain worker 才會對 Milvus drop 整個 collection。
2. N+1 → 1 — 舊版每 doc 一次 Milvus delete；新版單一 drop_collection 事件。

Atomicity 設計：use case 不持有 session（DDD 紅線）。
publish_outbox.execute 只 session.add 不 commit；後續 kb_repo.delete 內的
``atomic()`` context manager 結束時 await session.commit() 會帶上 publish 的
INSERT 一起持久化。任一環節 raise，atomic 內的 SAVEPOINT rollback 會把
publish 的 add 也一起丟掉 — 達成「兩個動作要嘛都成功要嘛都不寫」的 atomicity。
"""

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.outbox.events import vector_drop_collection_event


class DeleteKnowledgeBaseUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        publish_outbox_event_use_case: PublishOutboxEventUseCase,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        # 保留 doc_repo 介面（Phase B 暫時用不到，留作未來擴充：例如要先讀
        # children doc 帶進事件 payload。Phase A-B 範圍 drop_collection 不需要）
        self._doc_repo = document_repository
        self._publish_outbox = publish_outbox_event_use_case

    async def execute(self, kb_id: str, requester_tenant_id: str = "") -> None:
        # 防跨租戶刪除（含 system_admin bypass，由 ensure_kb_accessible 處理）
        kb, _ = await ensure_kb_accessible(
            self._kb_repo, kb_id, requester_tenant_id
        )

        # 1) Publish outbox event（session.add，不 commit）
        # 2) PG cascade delete（atomic 內 commit，帶上 publish 的 INSERT）
        # 順序很重要：publish 必須先呼叫，這樣 add 就排在 session 的 unit-of-work
        # 內，等 kb_repo.delete 的 atomic commit 一起 flush。
        event = vector_drop_collection_event(
            tenant_id=kb.tenant_id,
            aggregate_id=kb_id,
            collection=f"kb_{kb_id}",
        )
        await self._publish_outbox.execute(event)

        # PG cascade: chunks → documents → knowledge_base（kb_repo.delete 內已實作）
        await self._kb_repo.delete(kb_id)
