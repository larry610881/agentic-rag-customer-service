"""Token 狀態儲存 port（Issue #67 P3）

JWT 本身無狀態；要做「refresh 旋轉 + 重用偵測」與「改密碼即失效」，需要一點點
伺服器端狀態：

- RefreshTokenStore：每個 refresh **family**（一次登入）只承認最新一張 jti。
  拿舊 jti 來換票 = 重用（可能被竊）→ 整個 family 撤銷。
- TokenRevocationStore：改密碼 / 重設密碼時記下「user 的票 ver 必須 ≥ N」，
  access token 到期前就能擋掉舊票，不必每請求查 DB。
"""

from abc import ABC, abstractmethod
from enum import StrEnum


class RotationResult(StrEnum):
    OK = "ok"            # 舊 jti 相符，已換成新 jti
    REUSED = "reused"    # family 存在但 jti 不是最新 → 重用
    UNKNOWN = "unknown"  # family 不存在（登入早於本機制、或儲存遺失）


class RefreshTokenStore(ABC):
    @abstractmethod
    async def begin(self, family: str, jti: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def rotate(
        self, family: str, presented_jti: str, new_jti: str, ttl_seconds: int
    ) -> RotationResult: ...

    @abstractmethod
    async def revoke(self, family: str) -> None: ...


class TokenRevocationStore(ABC):
    @abstractmethod
    async def revoke_user_before(
        self, user_id: str, min_version: int, ttl_seconds: int
    ) -> None: ...

    @abstractmethod
    async def min_version(self, user_id: str) -> int | None: ...
