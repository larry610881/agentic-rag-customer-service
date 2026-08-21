"""BotConfigVersion — Bot 設定版本（append-only，config as commit）

狀態機（spec §4.1）：
    draft → validating → pending_publish → published
    draft → published（gate off / warn 強制）
    draft / pending_publish → rejected
版本列不可變：「修改 draft」= 建新 draft。is_current 唯一由 repository 保證。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.shared.exceptions import DomainException

# status
STATUS_DRAFT = "draft"
STATUS_VALIDATING = "validating"
STATUS_PENDING_PUBLISH = "pending_publish"
STATUS_PUBLISHED = "published"
STATUS_REJECTED = "rejected"

# source
SOURCE_MANUAL = "manual"
SOURCE_OPTIMIZER = "optimizer"
SOURCE_ROLLBACK = "rollback"
SOURCE_SEED = "seed"

# gate_verdict
VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_FORCED = "forced"   # warn 模式驗證失敗仍強制發布
VERDICT_SKIPPED = "skipped"  # gate 未啟用直接發布（含 rollback 免重驗）

_PUBLISHABLE = frozenset({STATUS_DRAFT, STATUS_PENDING_PUBLISH})
_REJECTABLE = frozenset({STATUS_DRAFT, STATUS_PENDING_PUBLISH})
_VALIDATABLE = frozenset({STATUS_DRAFT})


class GateBlockedError(DomainException):
    """閘門啟用時的操作被擋（interfaces 層對應 409）：
    版控欄位直改需走版本 API、驗證未過不可發布等。"""


class VersionConflictError(DomainException):
    """並發建版撞版本號唯一約束（interfaces 層對應 409）：重試多次仍衝突，
    請前端重新載入版本清單後再試（M2）。"""


class InvalidVersionTransitionError(DomainException):
    """非法的版本狀態轉移（interfaces 層對應 409）。"""

    def __init__(self, current: str, action: str) -> None:
        self.current = current
        self.action = action
        super().__init__(
            f"Cannot {action} a version in status '{current}'"
        )


@dataclass
class BotConfigVersion:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    bot_id: str = ""
    version_no: int = 1
    config_snapshot: dict = field(default_factory=dict)
    snapshot_schema: int = 1
    changed_fields: list[str] = field(default_factory=list)
    status: str = STATUS_DRAFT
    is_current: bool = False
    source: str = SOURCE_MANUAL
    source_run_id: str | None = None
    gate_run_id: str | None = None
    gate_verdict: str | None = None
    author_user_id: str | None = None
    published_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def mark_published(self, verdict: str) -> None:
        if self.status not in _PUBLISHABLE:
            raise InvalidVersionTransitionError(self.status, "publish")
        self.status = STATUS_PUBLISHED
        self.gate_verdict = verdict
        self.published_at = datetime.now(timezone.utc)
        # is_current 不在此設定：save(version) 會立即 commit，若此處先設 True，
        # 舊 current 尚未清除即違反 partial unique index ix_bcv_current（C1）。
        # is_current 的翻轉一律交給 repository.set_current 在單一交易內完成。

    def mark_rejected(self) -> None:
        if self.status not in _REJECTABLE:
            raise InvalidVersionTransitionError(self.status, "reject")
        self.status = STATUS_REJECTED

    def mark_validating(self, gate_run_id: str) -> None:
        if self.status not in _VALIDATABLE:
            raise InvalidVersionTransitionError(self.status, "validate")
        self.status = STATUS_VALIDATING
        self.gate_run_id = gate_run_id

    def mark_validation_aborted(self) -> None:
        """gate run 異常中止：退回 draft、不留 verdict（與 fail 區別）。"""
        if self.status == STATUS_VALIDATING:
            self.status = STATUS_DRAFT
            self.gate_run_id = None

    def mark_validation_result(self, *, passed: bool) -> None:
        """gate run 完成：通過 → pending_publish（人工發布，定案 1=B）；
        未通過 → 退回 draft（gate_run_id 保留供 UI 顯示失敗明細）。"""
        if self.status != STATUS_VALIDATING:
            raise InvalidVersionTransitionError(
                self.status, "complete-validation"
            )
        self.status = STATUS_PENDING_PUBLISH if passed else STATUS_DRAFT
        self.gate_verdict = VERDICT_PASS if passed else VERDICT_FAIL
