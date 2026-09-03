from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

API_ACCESS_TOKEN_TYPE = "api_access"


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
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_days = refresh_token_expire_days
        self._issuer = issuer
        self._audience = audience
        self._api_access_expire_seconds = api_access_expire_seconds

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
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": client_id,
            "type": API_ACCESS_TOKEN_TYPE,
            "tenant_id": tenant_id,
            "scopes": list(scopes),
            "bot_ids": list(bot_ids),
            "ver": version,
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=self._api_access_expire_seconds),
        }
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token, self._api_access_expire_seconds

    def create_tenant_token(self, tenant_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._access_token_expire_minutes
        )
        payload = {
            "sub": tenant_id,
            "exp": expire,
            "type": "tenant_access",
        }
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

    def create_user_token(
        self,
        user_id: str,
        tenant_id: str | None,
        role: str,
    ) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._access_token_expire_minutes
        )
        payload: dict[str, Any] = {
            "sub": user_id,
            "role": role,
            "exp": expire,
            "type": "user_access",
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str | None,
        role: str,
    ) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._refresh_token_expire_days
        )
        payload: dict[str, Any] = {
            "sub": user_id,
            "role": role,
            "exp": expire,
            "type": "refresh",
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

    def create_tenant_refresh_token(self, tenant_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._refresh_token_expire_days
        )
        payload = {
            "sub": tenant_id,
            "exp": expire,
            "type": "tenant_refresh",
        }
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

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
        # 帶 iss/aud 的票必須相符；legacy 票（無 iss/aud）維持可解析（P3 收緊）
        self._validate_issuer_audience(payload)
        return payload

    def _validate_issuer_audience(self, payload: dict[str, Any]) -> None:
        if "iss" in payload and payload["iss"] != self._issuer:
            raise ValueError("Invalid token: Invalid issuer")
        if "aud" in payload:
            aud = payload["aud"]
            auds = aud if isinstance(aud, list) else [aud]
            if self._audience not in auds:
                raise ValueError("Invalid token: Invalid audience")

