"""租戶 API key 用例（Issue #67 P2）

- Create / List / Revoke：租戶管理員管理自己租戶的 key；system_admin 可跨租戶。
- ExchangeClientCredentials：client_id + client_secret → api_access token（15 分鐘，
  不發 refresh；到期用 secret 再換）。
- AuthenticateApiClient：每個請求驗 ver 與存活狀態（撤銷即刻生效）。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.auth.api_key import (
    ApiKey,
    ApiPrincipal,
    InvalidClientError,
    generate_client_secret,
    hash_client_secret,
    new_salt,
    parse_scope_string,
    secret_display_prefix,
    validate_scopes,
)
from src.domain.auth.api_key_repository import ApiKeyRepository
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError

AUDIT_ENTITY = "api_key"


def _audit_view(key: ApiKey) -> dict:
    return {
        "name": key.name,
        "description": key.description,
        "scopes": list(key.scopes),
        "allowed_bot_ids": list(key.allowed_bot_ids),
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
        "token_version": key.token_version,
        "secret_prefix": key.secret_prefix,
    }


@dataclass(frozen=True)
class CreateApiKeyCommand:
    tenant_id: str
    name: str
    scopes: list[str]
    description: str = ""
    allowed_bot_ids: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    actor_user_id: str | None = None


@dataclass(frozen=True)
class CreateApiKeyResult:
    key: ApiKey
    client_secret: str  # 只在此刻回傳一次


class CreateApiKeyUseCase:
    def __init__(
        self,
        repo: ApiKeyRepository,
        env_label: str,
        audit: Any | None = None,
    ) -> None:
        self._repo = repo
        self._env_label = env_label
        self._audit = audit

    async def execute(self, command: CreateApiKeyCommand) -> CreateApiKeyResult:
        if not command.name.strip():
            raise ValidationError("name is required")
        scopes = validate_scopes(command.scopes)
        if not scopes:
            raise ValidationError("at least one scope is required")
        if command.expires_at is not None and command.expires_at <= datetime.now(
            timezone.utc
        ):
            raise ValidationError("expires_at must be in the future")

        secret = generate_client_secret(self._env_label)
        salt = new_salt()
        key = ApiKey(
            tenant_id=command.tenant_id,
            name=command.name.strip(),
            description=command.description,
            scopes=scopes,
            allowed_bot_ids=list(command.allowed_bot_ids),
            expires_at=command.expires_at,
            secret_hash=hash_client_secret(secret, salt),
            secret_salt=salt,
            secret_prefix=secret_display_prefix(secret),
            created_by=command.actor_user_id,
        )
        await self._repo.save(key)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=key.id,
                action="create",
                before=None,
                after=_audit_view(key),
                actor_user_id=command.actor_user_id,
                tenant_id=key.tenant_id,
            )
        return CreateApiKeyResult(key=key, client_secret=secret)


class ListApiKeysUseCase:
    def __init__(self, repo: ApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self, tenant_id: str | None) -> list[ApiKey]:
        if tenant_id is None:
            return await self._repo.list_all()
        return await self._repo.list_by_tenant(tenant_id)


class RevokeApiKeyUseCase:
    def __init__(self, repo: ApiKeyRepository, audit: Any | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(
        self,
        key_id: str,
        *,
        tenant_id: str | None,
        actor_user_id: str | None = None,
    ) -> ApiKey:
        """tenant_id=None 代表 system_admin 跨租戶；否則 key 必須屬於該租戶。"""
        key = await self._repo.find_by_id(key_id)
        if key is None or (tenant_id is not None and key.tenant_id != tenant_id):
            raise EntityNotFoundError("ApiKey", key_id)
        if key.revoked_at is not None:
            return key
        before = _audit_view(key)
        key.revoke()
        await self._repo.save(key)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=key.id,
                action="revoke",
                before=before,
                after=_audit_view(key),
                actor_user_id=actor_user_id,
                tenant_id=key.tenant_id,
            )
        return key


@dataclass(frozen=True)
class ClientCredentialsResult:
    access_token: str
    expires_in: int
    scope: str


class ExchangeClientCredentialsUseCase:
    def __init__(self, repo: ApiKeyRepository, jwt_service: Any) -> None:
        self._repo = repo
        self._jwt = jwt_service

    async def execute(
        self, *, client_id: str, client_secret: str, scope: str | None
    ) -> ClientCredentialsResult:
        key = await self._repo.find_by_id(client_id) if client_id else None
        # 不存在 / 撤銷 / 過期 / secret 錯：同一路徑、同一訊息
        if key is None or not key.is_active() or not key.verify_secret(client_secret):
            raise InvalidClientError()
        scopes = key.effective_scopes(parse_scope_string(scope))
        token, expires_in = self._jwt.create_api_access_token(
            client_id=key.id,
            tenant_id=key.tenant_id,
            scopes=scopes,
            bot_ids=list(key.allowed_bot_ids),
            version=key.token_version,
        )
        await self._repo.touch_last_used(key.id, datetime.now(timezone.utc))
        return ClientCredentialsResult(
            access_token=token, expires_in=expires_in, scope=" ".join(scopes)
        )


class AuthenticateApiClientUseCase:
    """api_access token 的每請求驗證：key 存活且 ver 相符。"""

    def __init__(self, repo: ApiKeyRepository) -> None:
        self._repo = repo

    async def execute(self, payload: dict) -> ApiPrincipal:
        client_id = payload.get("sub") or ""
        key = await self._repo.find_by_id(client_id) if client_id else None
        if key is None or not key.is_active():
            raise InvalidClientError()
        if payload.get("ver") != key.token_version:
            raise InvalidClientError()
        tenant_id = payload.get("tenant_id") or key.tenant_id
        if tenant_id != key.tenant_id:
            raise InvalidClientError()
        return ApiPrincipal(
            client_id=key.id,
            tenant_id=key.tenant_id,
            scopes=tuple(payload.get("scopes") or []),
            bot_ids=tuple(payload.get("bot_ids") or []),
        )
