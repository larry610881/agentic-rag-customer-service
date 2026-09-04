"""宿主身分綁定協定（Issue #68 P7b）

通用協定，不依網站客製：後台每租戶一把 identity secret
（可輪替、可停用、可選「強制驗證」）。
宿主後端算 ``hash = HMAC-SHA256(secret, f"{user_id}.{exp}")``（hex），前端呼叫
``widget.identify({userId, exp, hash, name?, email?})``；後端重算比對並檢查 exp。
通過 → userId 綁進 widget token，主體升級為 end_user；失敗 → 預設降級為匿名並計分，
租戶開「強制驗證」才拒絕。hash 只能在宿主後端算，secret 不得進前端。
"""

import hashlib
import hmac
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

IDENTITY_MAX_EXP_SKEW_SECONDS = 24 * 3600  # exp 最多可設未來 24 小時


@dataclass
class TenantIdentitySecret:
    tenant_id: str
    secret_encrypted: str
    is_enabled: bool = True
    enforce_verified: bool = False   # True：驗證失敗直接拒絕；False：降級為匿名
    rotated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TenantIdentitySecretRepository(ABC):
    @abstractmethod
    async def get(self, tenant_id: str) -> TenantIdentitySecret | None: ...

    @abstractmethod
    async def save(self, secret: TenantIdentitySecret) -> None: ...


def generate_identity_secret() -> str:
    return secrets.token_hex(32)


def compute_identity_hash(secret: str, user_id: str, exp: int) -> str:
    return hmac.new(
        secret.encode("utf-8"), f"{user_id}.{exp}".encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_identity(
    secret: str,
    user_id: str,
    exp: int,
    presented_hash: str,
    now: datetime | None = None,
) -> bool:
    """HMAC 相符且 exp 未過期、未超過 24 小時上限。"""
    now_ts = int((now or datetime.now(timezone.utc)).timestamp())
    if not user_id or exp <= now_ts or exp - now_ts > IDENTITY_MAX_EXP_SKEW_SECONDS:
        return False
    expected = compute_identity_hash(secret, user_id, exp)
    return hmac.compare_digest(expected, (presented_hash or "").lower())
