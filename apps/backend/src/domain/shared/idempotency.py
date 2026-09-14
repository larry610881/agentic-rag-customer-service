"""Idempotency-Key 重送保護的 domain 契約（Issue #95）。

快照 store 只存「第一次回應」：key 在保留期內重送回同一份結果。
對話 / 訊息 / 記帳仍以 Postgres 為唯一事實來源，store 不碰它們。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.domain.shared.exceptions import DomainException

STATE_IN_PROGRESS = "in_progress"
STATE_DONE = "done"


@dataclass(frozen=True)
class IdempotencyRecord:
    state: str  # in_progress | done
    fingerprint: str  # 請求 body 的 sha256；同 key 不同 body → 拒絕
    status: int | None = None
    body: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClaimOutcome:
    acquired: bool
    existing: IdempotencyRecord | None = None
    available: bool = True  # False = store 不可用 → 呼叫端 fail-open


class IdempotencyStore(Protocol):
    async def claim(
        self, key: str, fingerprint: str, ttl_seconds: int
    ) -> ClaimOutcome:
        """原子搶佔：第一次寫入成功 → acquired；已存在 → 回既有紀錄。"""
        ...

    async def complete(
        self, key: str, record: IdempotencyRecord, ttl_seconds: int
    ) -> None:
        """成功後以完成快照覆蓋處理中標記，並換成保留期 TTL。"""
        ...

    async def release(self, key: str) -> None:
        """失敗 / 非 2xx → 刪除，讓客戶端重送可真正重跑。"""
        ...


class IdempotencyKeyReused(DomainException):
    """同一把 key 送了不同的 body。"""

    def __init__(self) -> None:
        super().__init__(
            "Idempotency-Key was already used with a different request body"
        )


class IdempotencyInProgress(DomainException):
    """同一把 key 的第一次請求仍在處理中。"""

    def __init__(self) -> None:
        super().__init__("A request with this Idempotency-Key is still in progress")
