"""Eval dataset 資源歸屬檢查（C4–C7）。

eval_dataset 的讀/寫端點原本以純 dataset_id / case_id 查詢、不比對 tenant，造成
跨租戶讀取題集內容、竄改與刪除（含靜默停用平台通用集的安全題）。此模組統一歸屬語意：

- 讀（GET / export / eval / validate / run）：擁有者 or 平台通用集 or system_admin。
  平台集設計上供所有租戶讀取與執行（gate run 用），故允許跨租戶讀。
- 寫/刪（PUT / DELETE / test case CRUD）：system_admin 一律可；平台集非 admin →
  403（可讀不可改）；一般集非擁有者 → 404（不洩漏存在性）。

tenant_id 為 None 代表呼叫端未帶入（維持舊行為）；生產一律經 router 帶入。
"""

from __future__ import annotations

from src.domain.eval_dataset.entity import EvalDataset
from src.domain.shared.exceptions import AuthorizationError, EntityNotFoundError

SYSTEM_ADMIN_ROLE = "system_admin"


def can_read_dataset(
    ds: EvalDataset, tenant_id: str | None, role: str | None
) -> bool:
    if tenant_id is None or role == SYSTEM_ADMIN_ROLE:
        return True
    return ds.tenant_id == tenant_id or ds.is_platform_base


def ensure_dataset_read(
    ds: EvalDataset, tenant_id: str | None, role: str | None
) -> None:
    if not can_read_dataset(ds, tenant_id, role):
        raise EntityNotFoundError("EvalDataset", ds.id.value)


def ensure_dataset_write(
    ds: EvalDataset, tenant_id: str | None, role: str | None
) -> None:
    if tenant_id is None or role == SYSTEM_ADMIN_ROLE:
        return
    if ds.is_platform_base:
        # 可讀不可改：非 admin 不得修改/刪除平台通用集
        raise AuthorizationError("平台通用集僅 system_admin 可修改")
    if ds.tenant_id != tenant_id:
        raise EntityNotFoundError("EvalDataset", ds.id.value)
