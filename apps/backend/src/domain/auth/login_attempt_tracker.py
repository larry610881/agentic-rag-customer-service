"""登入失敗追蹤 port（Issue #58）

公開後台的登入頁需要帳號層級的失敗鎖定：同一識別（email）連續失敗達上限後
暫時拒絕登入。實作（Redis）負責計數與 TTL；use case 只依 retry_after 決策。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LoginLockoutPolicy:
    max_failures: int = 5
    failure_window_seconds: int = 900
    lockout_seconds: int = 900


class LoginAttemptTracker(ABC):
    @abstractmethod
    async def retry_after(self, identifier: str) -> int:
        """帳號目前被鎖定的剩餘秒數；0 表示未鎖定。"""

    @abstractmethod
    async def record_failure(self, identifier: str) -> int:
        """記錄一次失敗。若因此達上限而鎖定，回傳鎖定秒數；否則 0。"""

    @abstractmethod
    async def reset(self, identifier: str) -> None:
        """登入成功後清除失敗計數。"""
