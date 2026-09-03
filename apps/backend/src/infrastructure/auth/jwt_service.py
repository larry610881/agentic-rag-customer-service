"""JWT 簽發 / 驗證（Issue #67 P2/P3）

所有票種一律帶 iss / aud / jti / iat / type，header 帶 kid（支援 secret 輪替時辨識）。
- user_access / refresh：sub=user_id、tenant_id、role、ver（user.token_version）
- refresh 另帶 family + jti（旋轉 / 重用偵測）
- tenant_access / tenant_refresh：legacy 租戶票（sub=tenant_id）
- api_access：機器票（sub=client_id、scopes、bot_ids、ver）

驗證：簽章與 exp 必驗；帶 iss/aud 的票必須相符；不帶 iss 的 legacy 票只在
allow_legacy_tokens=True（development）時接受。
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

API_ACCESS_TOKEN_TYPE = "api_access"
WIDGET_TOKEN_TYPE = "widget_access"


class JWTService:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
        issuer: str = "agentic-rag",
        audience: str = "agentic-rag-api",
        api_access_expire_seconds: int = 900,
        key_id: str = "k1",
        allow_legacy_tokens: bool = True,
        widget_token_expire_seconds: int = 900,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_days = refresh_token_expire_days
        self._issuer = issuer
        self._audience = audience
        self._api_access_expire_seconds = api_access_expire_seconds
        self._key_id = key_id
        self._allow_legacy_tokens = allow_legacy_tokens
        self._widget_token_expire_seconds = widget_token_expire_seconds

    # ------------------------------------------------------------------ helpers

    @property
    def access_token_ttl_seconds(self) -> int:
        return self._access_token_expire_minutes * 60

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return self._refresh_token_expire_days * 86400

    def _base_claims(
        self, *, token_type: str, sub: str, ttl: timedelta, jti: str | None = None
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": sub,
            "type": token_type,
            "jti": jti or str(uuid4()),
            "iat": now,
            "exp": now + ttl,
        }

    def _encode(self, payload: dict[str, Any]) -> str:
        token: str = jwt.encode(
            payload,
            self._secret_key,
            algorithm=self._algorithm,
            headers={"kid": self._key_id},
        )
        return token

    # ------------------------------------------------------------------ issue

    def create_tenant_token(self, tenant_id: str) -> str:
        payload = self._base_claims(
            token_type="tenant_access",
            sub=tenant_id,
            ttl=timedelta(minutes=self._access_token_expire_minutes),
        )
        return self._encode(payload)

    def create_user_token(
        self,
        user_id: str,
        tenant_id: str | None,
        role: str,
        version: int | None = None,
    ) -> str:
        payload = self._base_claims(
            token_type="user_access",
            sub=user_id,
            ttl=timedelta(minutes=self._access_token_expire_minutes),
        )
        payload["role"] = role
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if version is not None:
            payload["ver"] = version
        return self._encode(payload)

    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str | None,
        role: str,
        version: int | None = None,
        family: str | None = None,
        jti: str | None = None,
    ) -> str:
        payload = self._base_claims(
            token_type="refresh",
            sub=user_id,
            ttl=timedelta(days=self._refresh_token_expire_days),
            jti=jti,
        )
        payload["role"] = role
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if version is not None:
            payload["ver"] = version
        if family is not None:
            payload["family"] = family
        return self._encode(payload)

    def create_tenant_refresh_token(
        self, tenant_id: str, family: str | None = None, jti: str | None = None
    ) -> str:
        payload = self._base_claims(
            token_type="tenant_refresh",
            sub=tenant_id,
            ttl=timedelta(days=self._refresh_token_expire_days),
            jti=jti,
        )
        if family is not None:
            payload["family"] = family
        return self._encode(payload)

    def create_api_access_token(
        self,
        *,
        client_id: str,
        tenant_id: str,
        scopes: list[str],
        bot_ids: list[str],
        version: int,
    ) -> tuple[str, int]:
        """機器票（Issue #67 P2）。

        claims：iss/aud/jti/iat/exp + tenant_id/scopes/bot_ids/ver。
        """
        payload = self._base_claims(
            token_type=API_ACCESS_TOKEN_TYPE,
            sub=client_id,
            ttl=timedelta(seconds=self._api_access_expire_seconds),
        )
        payload.update({
            "tenant_id": tenant_id,
            "scopes": list(scopes),
            "bot_ids": list(bot_ids),
            "ver": version,
        })
        return self._encode(payload), self._api_access_expire_seconds

    def create_widget_token(
        self,
        *,
        bot_id: str,
        tenant_id: str,
        origin: str,
        visitor_id: str,
    ) -> tuple[str, int]:
        """widget 短效票（Issue #67 P4）：綁 bot / Origin / visitor，無 refresh。"""
        payload = self._base_claims(
            token_type=WIDGET_TOKEN_TYPE,
            sub=bot_id,
            ttl=timedelta(seconds=self._widget_token_expire_seconds),
        )
        payload.update({
            "tenant_id": tenant_id,
            "origin": origin,
            "visitor_id": visitor_id,
        })
        return self._encode(payload), self._widget_token_expire_seconds

    # ------------------------------------------------------------------ verify

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"verify_aud": False, "verify_iss": False},
            )
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}") from e
        self._validate_issuer_audience(payload)
        return payload

    def _validate_issuer_audience(self, payload: dict[str, Any]) -> None:
        if "iss" not in payload:
            if self._allow_legacy_tokens:
                return  # P3 之前簽的票；production 不接受
            raise ValueError("Invalid token: missing issuer")
        if payload["iss"] != self._issuer:
            raise ValueError("Invalid token: Invalid issuer")
        aud = payload.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        if self._audience not in auds:
            raise ValueError("Invalid token: Invalid audience")
