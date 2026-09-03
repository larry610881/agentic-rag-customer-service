"""租戶 API key（機器憑證，Issue #67 P2）

四種主體各一種憑證：人（email+密碼）、機器（本檔：client_id + client_secret）、
widget（短效 widget token）、LINE（簽章）。機器憑證換得的 access token
type=api_access，帶 tenant_id / scopes / bot_ids / ver（token_version）。

secret 只在建立時回傳一次；DB 只存 sha256(salt + secret) 與前綴供後台辨識。
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.shared.exceptions import DomainException, ValidationError

# 冒號分層、動詞在後。kb:* 先保留名稱不實作。
API_SCOPES: frozenset[str] = frozenset({
    "chat:send",
    "chat:stream",
    "chat:history:read",
    "feedback:write",
    "bots:read",
    "kb:read",
    "kb:write",
})

SECRET_PREFIX = "ark"
_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SECRET_RANDOM_LEN = 32
_PREFIX_DISPLAY_LEN = 12  # "ark_dev_" 已 8 碼，再帶 4 碼隨機才有辨識度
API_CLIENT_ROLE = "api_client"


class InvalidClientError(DomainException):
    """client 不存在 / secret 錯 / 已撤銷 / 已過期 — 一律同一訊息，避免列舉。"""

    def __init__(self) -> None:
        super().__init__("invalid_client")


class InvalidScopeError(DomainException):
    def __init__(self, scopes: list[str] | None = None) -> None:
        super().__init__("invalid_scope")
        self.scopes = scopes or []


def generate_client_secret(env_label: str) -> str:
    rand = "".join(secrets.choice(_BASE62) for _ in range(_SECRET_RANDOM_LEN))
    return f"{SECRET_PREFIX}_{env_label}_{rand}"


def new_salt() -> str:
    return secrets.token_hex(16)


def hash_client_secret(secret: str, salt: str) -> str:
    return hashlib.sha256((salt + secret).encode("utf-8")).hexdigest()


def secret_display_prefix(secret: str) -> str:
    return secret[:_PREFIX_DISPLAY_LEN]


def validate_scopes(scopes: list[str]) -> list[str]:
    unknown = sorted(set(scopes) - API_SCOPES)
    if unknown:
        raise ValidationError(f"Unknown scopes: {', '.join(unknown)}")
    # 去重、保序
    seen: list[str] = []
    for s in scopes:
        if s not in seen:
            seen.append(s)
    return seen


def parse_scope_string(scope: str | None) -> list[str] | None:
    """OAuth2 `scope` 參數：空白分隔；None / 空字串 = 未指定。"""
    if scope is None or not scope.strip():
        return None
    return scope.split()


@dataclass
class ApiKey:
    tenant_id: str
    name: str
    secret_hash: str
    secret_salt: str
    secret_prefix: str
    id: str = field(default_factory=lambda: str(uuid4()))  # = client_id
    description: str = ""
    scopes: list[str] = field(default_factory=list)
    allowed_bot_ids: list[str] = field(default_factory=list)  # 空 = 該租戶所有 bot
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    token_version: int = 1
    last_used_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def client_id(self) -> str:
        return self.id

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True

    def verify_secret(self, secret: str) -> bool:
        candidate = hash_client_secret(secret, self.secret_salt)
        return hmac.compare_digest(candidate, self.secret_hash)

    def allows_bot(self, bot_id: str | None) -> bool:
        if not self.allowed_bot_ids:
            return True
        return bot_id is not None and bot_id in self.allowed_bot_ids

    def grants(self, scopes: list[str]) -> bool:
        return set(scopes) <= set(self.scopes)

    def effective_scopes(self, requested: list[str] | None) -> list[str]:
        """換票時：未指定 = key 全部 scopes；超出 key 範圍 → invalid_scope。"""
        if requested is None:
            return list(self.scopes)
        if not self.grants(requested):
            raise InvalidScopeError(sorted(set(requested) - set(self.scopes)))
        return validate_scopes(requested)

    def revoke(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        self.revoked_at = now
        self.token_version += 1  # 已發出的 access token（ver 舊值）立即失效
        self.updated_at = now


@dataclass(frozen=True)
class ApiPrincipal:
    """api_access token 驗證後的呼叫者身分（放進 CurrentTenant）。"""

    client_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    bot_ids: tuple[str, ...]

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def allows_bot(self, bot_id: str | None) -> bool:
        if not self.bot_ids:
            return True
        return bot_id is not None and bot_id in self.bot_ids
