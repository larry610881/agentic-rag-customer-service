"""Admin KB cross-tenant access helper.

統一 8 個 use case 的「KB 歸屬檢查 + system_admin bypass」邏輯，避免 drift。

之前 8 個 use case 各自寫 `if kb is None or kb.tenant_id != tenant_id: raise`
→ admin (tenant_id=SYSTEM_TENANT_ID) 想看其他租戶 KB 全部 404
→ Milvus 管理 / KB Studio / Quality / Categories / Retrieval Playground 全爆

修法：用 ensure_kb_accessible() 統一，回傳 effective_tenant_id：
- 同租戶：等於 requester_tenant_id
- system_admin：等於 kb.tenant_id（真實 owner）
  → Milvus filter / chunk owner 都用此值，admin 看到正確租戶資料
"""

from __future__ import annotations

from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import EntityNotFoundError


def is_system_admin(requester_tenant_id: str) -> bool:
    """Check if requester is system_admin (bound to SYSTEM_TENANT_ID).

    用於 chunk / document / category 等 entity 層 tenant 檢查 bypass。
    """
    return requester_tenant_id == SYSTEM_TENANT_ID


def tenant_match_or_admin(
    entity_tenant_id: str,
    requester_tenant_id: str,
) -> bool:
    """True if 同租戶 or system_admin bypass。給 entity 層 if-guard 用。

    範例：
        if not tenant_match_or_admin(chunk.tenant_id, command.tenant_id):
            raise EntityNotFoundError("chunk", chunk_id)
    """
    if requester_tenant_id == SYSTEM_TENANT_ID:
        return True
    return entity_tenant_id == requester_tenant_id


async def ensure_kb_accessible(
    kb_repo: KnowledgeBaseRepository,
    kb_id: str,
    requester_tenant_id: str,
) -> tuple[KnowledgeBase, str]:
    """Validate requester can access KB; return (kb, effective_tenant_id).

    effective_tenant_id：
    - 同租戶 → requester_tenant_id
    - system_admin → kb.tenant_id (真實 owner，給 Milvus filter / chunk write 用)

    Raises:
        EntityNotFoundError: KB 不存在 OR 跨租戶（非 admin）— 統一 404 防枚舉
    """
    kb = await kb_repo.find_by_id(kb_id)
    if kb is None:
        raise EntityNotFoundError("kb", kb_id)
    # system_admin bypass：要求方掛 SYSTEM_TENANT_ID 即放行
    if is_system_admin(requester_tenant_id):
        return kb, kb.tenant_id
    # 同租戶
    if kb.tenant_id == requester_tenant_id:
        return kb, requester_tenant_id
    # 跨租戶非 admin → 404 防枚舉（不暴露 KB 存在但權限不對）
    raise EntityNotFoundError("kb", kb_id)
